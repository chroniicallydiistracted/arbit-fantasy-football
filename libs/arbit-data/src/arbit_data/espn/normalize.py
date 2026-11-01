"""The sole ESPN-to-canonical boundary: native facts, explicit scopes and immutable policy."""

from decimal import ROUND_HALF_UP, Decimal, DecimalException
from typing import Any, Literal
from uuid import UUID

from arbit_core.identity import EntityKind, ProviderRef
from sqlalchemy import Connection

from arbit_data.contracts import LeagueSnapshotCandidate, RosterEntry
from arbit_data.espn.contracts import EspnAcquisition, League, PoolEntry
from arbit_data.espn.reader import _validate_league
from arbit_data.espn.scoring_rules import normalize_scoring, role_for_position
from arbit_data.identities import resolve_native
from arbit_data.league import (
    DraftPick,
    FantasyTeam,
    LeagueDocument,
    Manager,
    Matchup,
    MatchupSide,
    NflTeam,
    Player,
    content_hash,
)

POSITIONS: dict[int, Literal["QB", "RB", "WR", "TE", "K", "DST"]] = {
    1: "QB",
    2: "RB",
    3: "WR",
    4: "TE",
    5: "K",
    16: "DST",
}
SLOTS = {
    0: "QB",
    1: "TQB",
    2: "RB",
    3: "RB_WR",
    4: "WR",
    5: "WR_TE",
    6: "TE",
    7: "OP",
    8: "DT",
    9: "DE",
    10: "LB",
    11: "DL",
    12: "CB",
    13: "S",
    14: "DB",
    15: "DP",
    16: "DST",
    17: "K",
    18: "P",
    19: "HC",
    20: "BENCH",
    21: "IR",
    23: "FLEX",
    24: "RESERVE",
    25: "ROOKIE",
}


def slot_name(source: int) -> str:
    return SLOTS.get(source, f"UNKNOWN_ESPN_SLOT_{source}")


def native_ref(kind: EntityKind, source: int | str, season: int) -> ProviderRef:
    scope = (
        f"ffa:1729878439:season:{season}"
        if kind in ("fantasy_team", "fantasy_matchup")
        else "global"
    )
    return ProviderRef(provider="espn", entity_kind=kind, external_id=str(source), scope=scope)


def scoring_context(league: League) -> tuple[str, dict[str, Any]]:
    normalized = normalize_scoring(
        league.settings.scoring_settings.model_dump(mode="json", by_alias=True), league.season_id
    )
    if not normalized.supported:
        raise ValueError("UNSUPPORTED_RULES")
    # The completed-lineup proof also depends on roster composition and period mapping.
    support = {
        "configHash": normalized.config_hash,
        "athleteRulesHash": normalized.athlete_rules.content_hash,
        "defenseRulesHash": normalized.defense_rules.content_hash,
    }
    return content_hash(
        {
            "season": league.season_id,
            **support,
            "slots": league.settings.roster_settings.lineup_slot_counts,
            "periods": league.settings.schedule_settings.get("matchupPeriods"),
            "size": league.settings.size,
        }
    ), support


def rule_material(league: League) -> tuple[str, dict[str, Any], str]:
    scoring_key, support = scoring_context(league)
    normalized = normalize_scoring(
        league.settings.scoring_settings.model_dump(mode="json", by_alias=True), league.season_id
    )
    settings = league.settings
    payload = {
        "format": "ffa-rules-v1",
        "season": league.season_id,
        "team_count": league.settings.size,
        "scoring_context_hash": scoring_key,
        "scoring": support,
        "athlete_rules": normalized.athlete_rules.model_dump(mode="json"),
        "defense_rules": normalized.defense_rules.model_dump(mode="json"),
        "lineup_slots": {
            slot_name(int(k)): v
            for k, v in sorted(settings.roster_settings.lineup_slot_counts.items())
            if v > 0
        },
        "lineup_lock_type": settings.roster_settings.lineup_locktime_type,
        "waiver_type": settings.acquisition_settings.get("acquisitionType"),
        "waiver_hours": settings.acquisition_settings.get("waiverHours"),
        "draft_type": settings.draft_settings.get("type"),
        "draft_order_type": settings.draft_settings.get("orderType"),
        "provider_policy": {
            name: settings.model_dump(mode="json", by_alias=True)[name]
            for name in (
                "rosterSettings",
                "acquisitionSettings",
                "tradeSettings",
                "draftSettings",
                "scheduleSettings",
            )
        },
        "recommendations_enabled": False,
    }
    return content_hash(payload), payload, scoring_key


def _actual_points(pool: PoolEntry, season: int, period: int) -> Decimal | None:
    blocks = [
        b
        for b in pool.player.stats
        if b.season_id == season
        and b.scoring_period_id == period
        and b.stat_source_id == 0
        and b.stat_split_type_id == 1
    ]
    if len(blocks) > 1:
        raise ValueError("AMBIGUOUS_ACTUAL_POINTS")
    value = blocks[0].applied_total if blocks else None
    try:
        return (
            value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if value is not None else None
        )
    except DecimalException:
        raise ValueError("INVALID_ACTUAL_POINTS") from None


def normalize_acquisition(
    connection: Connection, acquisition: EspnAcquisition, manifest_hash: str, rules_hash: str
) -> tuple[LeagueDocument, LeagueSnapshotCandidate]:
    league = acquisition.league
    if (
        league.id != 1729878439
        or league.game_id != 1
        or league.segment_id != 0
        or not league.settings.is_public
        or league.scoring_period_id != league.status.latest_scoring_period
    ):
        raise ValueError("INVALID_LEAGUE_SCOPE")
    _validate_league(league)
    season = league.season_id
    member_ids = {m.id for m in league.members}
    if (
        not member_ids
        or len(member_ids) != len(league.members)
        or any(
            not t.owners
            or len(set(t.owners)) != len(t.owners)
            or not set(t.owners) <= member_ids
            or t.primary_owner is not None
            and t.primary_owner not in t.owners
            for t in league.teams
        )
    ):
        raise ValueError("UNRESOLVED_MANAGER")
    # All profiles used by rosters, the available pool and the draft must be observed, never guessed.
    owned = {e.player_id: (t.id, e) for t in league.teams for e in t.roster.entries}
    pools = [e.player_pool_entry for t in league.teams for e in t.roster.entries] + list(
        acquisition.available
    )
    if len({p.id for p in pools}) != len(pools) or any(
        p.id == 0
        or p.id != p.player.id
        or (p.id not in owned and (p.on_team_id != 0 or p.status not in ("FREEAGENT", "WAIVERS")))
        for p in pools
    ):
        raise ValueError("INCONSISTENT_PLAYER_POOL")
    profiles = {p.id: p for p in pools}
    if any(
        p.player_id is not None and p.player_id not in profiles for p in league.draft_detail.picks
    ):
        raise ValueError("UNRESOLVED_DRAFT_PROFILE")
    roles = {p.id: role_for_position(p.player.default_position_id) for p in pools}
    if any((pid < 0) != (role == "defense_unit") for pid, role in roles.items()):
        raise ValueError("INCONSISTENT_PLAYER_KIND")
    if any(
        p.player.pro_team_id < 0 or roles[p.id] == "defense_unit" and p.player.pro_team_id == 0
        for p in pools
    ):
        raise ValueError("UNRESOLVED_NFL_TEAM")
    refs = (
        [native_ref("fantasy_team", t.id, season) for t in league.teams]
        + [native_ref("manager", m.id, season) for m in league.members]
        + [native_ref("fantasy_matchup", m.id, season) for m in league.schedule]
    )
    refs += [native_ref(roles[p.id], p.id, season) for p in pools]
    nfl_ids = sorted({p.player.pro_team_id for p in pools if p.player.pro_team_id > 0})
    refs += [native_ref("nfl_team", i, season) for i in nfl_ids]
    ids = resolve_native(connection, refs, acquisition.capture_started_at, manifest_hash)

    def identity(kind: EntityKind, source: int | str) -> UUID:
        return ids[native_ref(kind, source, season)]

    teams = []
    for team in sorted(league.teams, key=lambda t: t.id):
        record = team.record.overall
        teams.append(
            FantasyTeam(
                id=identity("fantasy_team", team.id),
                name=team.name,
                abbreviation=team.abbrev,
                managers=tuple(identity("manager", m) for m in sorted(team.owners)),
                primary_manager=identity("manager", team.primary_owner)
                if team.primary_owner
                else None,
                wins=record.wins,
                losses=record.losses,
                ties=record.ties,
                points_for=record.points_for,
                points_against=record.points_against,
                waiver_rank=team.waiver_rank,
                playoff_seed=team.playoff_seed,
            )
        )
    players = []
    for pool in sorted(pools, key=lambda p: p.id):
        player = pool.player
        owner_id, entry = owned[pool.id] if pool.id in owned else (None, None)
        players.append(
            Player(
                id=identity(roles[pool.id], pool.id),
                kind=roles[pool.id],
                display_name=player.full_name,
                position=POSITIONS[player.default_position_id],
                nfl_team_id=identity("nfl_team", player.pro_team_id)
                if player.pro_team_id
                else None,
                eligible_slots=tuple(slot_name(s) for s in sorted(set(player.eligible_slots))),
                active=player.active,
                injured=player.injured,
                injury_status=player.injury_status,
                availability="owned"
                if owner_id is not None
                else "waivers"
                if pool.status == "WAIVERS"
                else "free_agent",
                team_id=identity("fantasy_team", owner_id) if owner_id is not None else None,
                lineup_slot=slot_name(entry.lineup_slot_id) if entry else None,
                lineup_locked=pool.lineup_locked,
                roster_locked=pool.roster_locked,
                trade_locked=pool.trade_locked,
                official_current_points=_actual_points(pool, season, league.scoring_period_id),
            )
        )
    mapping = league.settings.schedule_settings.get("matchupPeriods", {})
    matchups = []
    for m in sorted(league.schedule, key=lambda m: m.id):
        periods = mapping.get(str(m.matchup_period_id))
        if (
            not isinstance(periods, list)
            or not periods
            or any(type(p) is not int or p < 1 for p in periods)
        ):
            raise ValueError("UNKNOWN_MATCHUP_PERIOD_MAPPING")
        matchups.append(
            Matchup(
                id=identity("fantasy_matchup", m.id),
                matchup_period=m.matchup_period_id,
                scoring_periods=tuple(periods),
                home=MatchupSide(
                    team_id=identity("fantasy_team", m.home.team_id),
                    official_points=m.home.total_points,
                )
                if m.home
                else None,
                away=MatchupSide(
                    team_id=identity("fantasy_team", m.away.team_id),
                    official_points=m.away.total_points,
                )
                if m.away
                else None,
            )
        )
    document = LeagueDocument(
        season=season,
        scoring_period=league.scoring_period_id,
        matchup_period=league.status.current_matchup_period,
        rules_hash=rules_hash,
        managers=tuple(
            Manager(
                id=identity("manager", m.id),
                display_name=m.display_name,
                first_name=(m.first_name.strip() or None) if m.first_name else None,
            )
            for m in sorted(league.members, key=lambda m: m.id)
        ),
        teams=tuple(teams),
        nfl_teams=tuple(NflTeam(id=identity("nfl_team", i)) for i in nfl_ids),
        players=tuple(players),
        matchups=tuple(matchups),
        draft_completed=league.draft_detail.drafted,
        draft_in_progress=league.draft_detail.in_progress,
        draft_picks=tuple(
            DraftPick(
                overall=p.overall_pick_number,
                round=p.round_id,
                pick_in_round=p.round_pick_number,
                team_id=identity("fantasy_team", p.team_id),
                player_id=identity(roles[p.player_id], p.player_id)
                if p.player_id is not None
                else None,
                keeper=p.keeper,
            )
            for p in sorted(league.draft_detail.picks, key=lambda p: p.overall_pick_number)
        ),
    )
    candidate = LeagueSnapshotCandidate(
        league_id="1729878439",
        season=season,
        observed_at=acquisition.capture_started_at,
        complete=True,
        rules_hash=rules_hash,
        manifest_hash=manifest_hash,
        teams=tuple(t.id for t in document.teams),
        roster=tuple(
            RosterEntry(entity_id=p.id, team_id=p.team_id, slot=p.lineup_slot)
            for p in document.players
            if p.team_id is not None and p.lineup_slot is not None
        ),
        available=tuple(p.id for p in document.players if p.team_id is None),
    )
    return document, candidate
