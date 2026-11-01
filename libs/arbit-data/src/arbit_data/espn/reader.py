"""Current-period public acquisition, distinct from canonical snapshot publication."""

from typing import Any, Protocol

from pydantic import ValidationError

from arbit_data.espn.contracts import AvailablePage, EspnAcquisition, League, PoolEntry
from arbit_data.espn.transport import EspnError, FetchResult, utc_now

PAGE_SIZE = 300
MAX_PAGES = 20
LEAGUE_VIEWS = ("mSettings", "mTeam", "mRoster", "mMatchupScore", "mDraftDetail", "mStatus")


class LeagueTransport(Protocol):
    def get(
        self,
        season: int,
        *,
        views: tuple[str, ...],
        scoring_period: int | None = None,
        fantasy_filter: dict[str, object] | None = None,
    ) -> FetchResult: ...


def _parse_league(result: FetchResult, season: int, period: int | None) -> League:
    try:
        league = League.model_validate(result.payload)
    except ValidationError:
        raise EspnError("SCHEMA_DRIFT") from None
    if league.id != 1729878439 or league.game_id != 1 or league.segment_id != 0:
        raise EspnError("SCHEMA_DRIFT")
    if league.season_id != season or (period is not None and league.scoring_period_id != period):
        raise EspnError("SCOPE_MISMATCH")
    if not league.settings.is_public:
        raise EspnError("ACCESS_DENIED")
    if (
        not league.status.first_scoring_period
        <= league.scoring_period_id
        <= league.status.final_scoring_period
    ):
        raise EspnError("SCOPE_MISMATCH")
    _validate_league(league)
    return league


def _validate_league(league: League) -> None:
    teams = {team.id for team in league.teams}
    if len(teams) != len(league.teams) or len(teams) != league.settings.size:
        raise EspnError("INCONSISTENT_DATA")
    owned: set[int] = set()
    for team in league.teams:
        for entry in team.roster.entries:
            pool = entry.player_pool_entry
            if (
                entry.player_id in owned
                or entry.player_id == 0
                or entry.player_id != pool.id
                or pool.id != pool.player.id
                or pool.on_team_id != team.id
                or pool.status != "ONTEAM"
            ):
                raise EspnError("INCONSISTENT_DATA")
            owned.add(entry.player_id)
    matchups: set[int] = set()
    for matchup in league.schedule:
        if matchup.id in matchups or (matchup.home is None and matchup.away is None):
            raise EspnError("INCONSISTENT_DATA")
        matchups.add(matchup.id)
        sides = [side.team_id for side in (matchup.home, matchup.away) if side is not None]
        if any(team_id not in teams for team_id in sides) or len(set(sides)) != len(sides):
            raise EspnError("INCONSISTENT_DATA")
    picks: set[int] = set()
    for pick in league.draft_detail.picks:
        if pick.team_id not in teams or pick.overall_pick_number in picks:
            raise EspnError("INCONSISTENT_DATA")
        picks.add(pick.overall_pick_number)


def _context(league: League) -> tuple[Any, ...]:
    rosters = sorted(
        (
            team.id,
            entry.player_id,
            entry.lineup_slot_id,
            entry.player_pool_entry.on_team_id,
            entry.player_pool_entry.status,
            entry.player_pool_entry.lineup_locked,
            entry.player_pool_entry.roster_locked,
            entry.player_pool_entry.trade_locked,
            entry.player_pool_entry.player.pro_team_id,
            tuple(sorted(entry.player_pool_entry.player.eligible_slots)),
            entry.player_pool_entry.player.injured,
            entry.player_pool_entry.player.injury_status,
        )
        for team in league.teams
        for entry in team.roster.entries
    )
    return (
        league.settings,
        league.status,
        league.scoring_period_id,
        tuple(sorted(team.id for team in league.teams)),
        rosters,
        league.draft_detail,
        tuple(
            sorted((member.id, member.display_name, member.first_name) for member in league.members)
        ),
        tuple(
            sorted(
                (team.id, team.name, team.abbrev, tuple(sorted(team.owners)), team.primary_owner)
                for team in league.teams
            )
        ),
    )


class EspnReader:
    def __init__(self, transport: LeagueTransport):
        self._transport = transport

    def fetch_league_snapshot(
        self, season: int, scoring_period: int | None = None
    ) -> EspnAcquisition:
        """Fetch complete pages and verify stable bracketing context, without claiming atomicity."""
        if type(season) is not int or not 2026 <= season <= 2100:
            raise ValueError("Explicit supported season required")
        if scoring_period is not None and (
            type(scoring_period) is not int or not 1 <= scoring_period <= 99
        ):
            raise ValueError("Scoring period must be an integer from 1 to 99")
        started = utc_now()
        first = self._transport.get(season, views=LEAGUE_VIEWS, scoring_period=scoring_period)
        league = _parse_league(first, season, scoring_period)
        period = league.scoring_period_id
        # The player pool is current ownership even if a historical period is requested.
        if period != league.status.latest_scoring_period:
            raise EspnError("HISTORICAL_AVAILABILITY_UNSUPPORTED")
        owned = {entry.player_id for team in league.teams for entry in team.roster.entries}
        seen: set[int] = set()
        available: list[PoolEntry] = []
        receipts = [first.receipt]
        offset = 0
        for _ in range(MAX_PAGES):
            fetched = self._transport.get(
                season,
                views=("kona_player_info",),
                scoring_period=period,
                fantasy_filter={
                    "players": {
                        "filterStatus": {"value": ["FREEAGENT", "WAIVERS"]},
                        "limit": PAGE_SIZE,
                        "offset": offset,
                        "sortPercOwned": {"sortPriority": 1, "sortAsc": False},
                    }
                },
            )
            receipts.append(fetched.receipt)
            try:
                page = AvailablePage.model_validate(fetched.payload)
            except ValidationError:
                raise EspnError("SCHEMA_DRIFT") from None
            if len(page.players) > PAGE_SIZE:
                raise EspnError("INCONSISTENT_DATA")
            for pool in page.players:
                if (
                    pool.id == 0
                    or pool.id != pool.player.id
                    or pool.id in seen
                    or pool.id in owned
                    or pool.on_team_id != 0
                    or pool.status not in ("FREEAGENT", "WAIVERS")
                ):
                    raise EspnError("INCONSISTENT_DATA")
                seen.add(pool.id)
                available.append(pool)
            if not page.players:
                break
            offset += len(page.players)
        else:
            raise EspnError("PAGE_LIMIT")
        last = self._transport.get(season, views=LEAGUE_VIEWS, scoring_period=period)
        final = _parse_league(last, season, period)
        receipts.append(last.receipt)
        if _context(league) != _context(final):
            raise EspnError("SOURCE_CHANGED")
        return EspnAcquisition(league, tuple(available), tuple(receipts), started, utc_now())
