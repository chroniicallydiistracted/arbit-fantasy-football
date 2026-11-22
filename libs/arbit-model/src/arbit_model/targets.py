"""Historical FFA targets: what each player-game and D/ST team-game was worth under FFA's rules.

Lines come from `arbit_data.nflverse.stat_lines` and are scored only by `arbit_core.scoring.score`
under the stored FFA rules (ADR-006). Participation labels separate a player who played without a
recorded statistic from one who did not play. Everything here is a pure function over rows;
reading and storage belong to the caller.
"""

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from decimal import Decimal
from typing import Any, Literal

from arbit_core.rules import RuleSet, StatLine
from arbit_core.scoring import MissingStatError, UnsupportedRuleError, score
from arbit_data.nflverse.stat_lines import (
    ATHLETE_COLUMNS,
    GameEvents,
    SourcedStatLine,
    athlete_line,
    defense_line,
    game_events,
)

TARGETS_VERSION = "arbit-ffa-targets-v1"

STAT_COLUMNS = tuple(sorted({column for columns in ATHLETE_COLUMNS.values() for column in columns}))
NO_STATISTICS_SOURCE = "participation:snaps_without_statistics_row"
TWO_POINT_RETURNS = "returns.two_point_returns"

Row = Mapping[str, Any]
Label = Literal[
    "played",
    "active_no_snaps",
    "inactive",
    "rostered_no_snaps",
    "not_active_roster",
    "unknown",
]
Basis = Literal["statistics", "snaps_without_statistics", "team_statistics"]


@dataclass(frozen=True)
class SeasonRows:
    """One season's nflverse rows. Snap counts are empty before 2013."""

    season: int
    games: Sequence[Row]  # schedules
    plays: Sequence[Row]  # play-by-play, at least `stat_lines.PLAY_COLUMNS`
    players: Sequence[Row]  # stats_player_week
    teams: Sequence[Row]  # stats_team_week
    snaps: Sequence[Row]  # snap_counts
    rosters: Sequence[Row]  # weekly rosters
    pfr_to_gsis: Mapping[str, str]


@dataclass(frozen=True)
class Participation:
    season: int
    week: int
    season_type: str
    game_id: str
    team: str
    player_id: str
    label: Label
    evidence: str
    roster_status: str | None
    position: str | None
    offense_snaps: float | None
    defense_snaps: float | None
    st_snaps: float | None


@dataclass(frozen=True)
class Target:
    role: Literal["athlete", "defense"]
    season: int
    week: int
    season_type: str
    game_id: str
    team: str
    opponent: str
    player_id: str | None
    position: str | None
    game_position: str | None
    basis: Basis
    line: SourcedStatLine
    points: Decimal | None
    refusal: str | None
    contributions: tuple[tuple[str, str, Decimal], ...]


@dataclass(frozen=True)
class _Game:
    game_id: str
    week: int
    season_type: str
    home: str
    away: str
    home_score: int
    away_score: int

    def opponent(self, team: str) -> str:
        return self.away if team == self.home else self.home


def _games(rows: SeasonRows) -> dict[str, _Game]:
    """Completed games of the season, regular and postseason."""
    games = {}
    for g in rows.games:
        if g.get("season") != rows.season or g.get("home_score") is None:
            continue
        games[str(g["game_id"])] = _Game(
            game_id=str(g["game_id"]),
            week=int(g["week"]),
            season_type="REG" if g.get("game_type") == "REG" else "POST",
            home=str(g["home_team"]),
            away=str(g["away_team"]),
            home_score=int(g["home_score"]),
            away_score=int(g["away_score"]),
        )
    return games


def _snaps(rows: SeasonRows) -> dict[tuple[str, str], Row]:
    by_player: dict[tuple[str, str], Row] = {}
    for snap in rows.snaps:
        gsis = rows.pfr_to_gsis.get(str(snap.get("pfr_player_id") or ""))
        if gsis is not None:
            by_player[(str(snap["game_id"]), gsis)] = snap
    return by_player


def _float(value: Any) -> float | None:
    return None if value is None or value != value else float(value)


def _snap_total(snap: Row | None) -> float:
    if snap is None:
        return 0.0
    return sum(_float(snap.get(k)) or 0.0 for k in ("offense_snaps", "defense_snaps", "st_snaps"))


def participation(rows: SeasonRows) -> list[Participation]:
    """Whether each rostered player played each of his team's completed games, and the evidence.

    Played: a snap in any phase, or a recorded statistic. Inactive: weekly roster status `INA`.
    Active without snaps: status `ACT`, no snap and no statistic, in a season whose rosters mark
    inactives and whose snap counts cover the player. Seasons without `INA` cannot separate
    inactive from active, so those players are `rostered_no_snaps`. Without snap counts, or
    without a PFR ID to join them, a player with no statistic is `unknown`. Other statuses
    (reserve, practice squad, released) are `not_active_roster`.
    """
    games = _games(rows)
    by_team_week: dict[tuple[str, int], _Game] = {}
    for game in games.values():
        by_team_week[(game.home, game.week)] = game
        by_team_week[(game.away, game.week)] = game
    snaps = _snaps(rows)
    stats = {(str(r["game_id"]), str(r["player_id"])) for r in rows.players if r.get("player_id")}
    marks_inactives = any(r.get("status") == "INA" for r in rows.rosters)
    joinable = set(rows.pfr_to_gsis.values()) if rows.snaps else set()
    labels: dict[tuple[str, str], Participation] = {}

    def add(game: _Game, team: str, gsis: str, status: str | None, position: str | None) -> None:
        key = (game.game_id, gsis)
        if key in labels:
            return
        snap = snaps.get(key)
        label: Label
        if _snap_total(snap) > 0:
            label, evidence = "played", "snap_counts"
        elif key in stats:
            label, evidence = "played", "statistics"
        elif status == "INA":
            label, evidence = "inactive", "weekly_rosters"
        elif status not in (None, "ACT"):
            label, evidence = "not_active_roster", "weekly_rosters"
        elif gsis not in joinable:
            label, evidence = "unknown", "no_snap_counts_for_player"
        elif not marks_inactives:
            label, evidence = "rostered_no_snaps", "weekly_rosters_without_inactives"
        else:
            label, evidence = "active_no_snaps", "weekly_rosters+snap_counts"
        labels[key] = Participation(
            season=rows.season,
            week=game.week,
            season_type=game.season_type,
            game_id=game.game_id,
            team=team,
            player_id=gsis,
            label=label,
            evidence=evidence,
            roster_status=status,
            position=str(snap["position"]) if snap is not None else position,
            offense_snaps=_float(snap.get("offense_snaps")) if snap is not None else None,
            defense_snaps=_float(snap.get("defense_snaps")) if snap is not None else None,
            st_snaps=_float(snap.get("st_snaps")) if snap is not None else None,
        )

    for roster in rows.rosters:
        gsis, team = roster.get("gsis_id"), str(roster.get("team") or "")
        scheduled = by_team_week.get((team, int(roster["week"])))
        if gsis and scheduled is not None:
            add(scheduled, team, str(gsis), roster.get("status"), roster.get("position"))
    # Players who played without a weekly roster row for that team and week.
    for (game_id, gsis), snap in snaps.items():
        if game_id in games and _snap_total(snap) > 0:
            add(games[game_id], str(snap["team"]), gsis, None, None)
    for r in rows.players:
        game_id = str(r["game_id"])
        if r.get("player_id") and game_id in games:
            add(games[game_id], str(r["team"]), str(r["player_id"]), None, r.get("position"))
    return sorted(labels.values(), key=lambda p: (p.week, p.game_id, p.team, p.player_id))


def _scored(
    line: SourcedStatLine, rules: RuleSet
) -> tuple[Decimal | None, str | None, tuple[tuple[str, str, Decimal], ...]]:
    try:
        breakdown = score(line.line, rules)
    except (MissingStatError, UnsupportedRuleError) as error:
        return None, f"{type(error).__name__}: {error}", ()
    parts = tuple((c.rule_id, c.stat_id, c.points) for c in breakdown.contributions)
    return breakdown.total, None, parts


def rule_out_two_point_returns(line: SourcedStatLine, snap: Row | None) -> SourcedStatLine:
    """R-061: a player with no defensive or special-teams snap did not return a two-point try.

    Only a recorded snap row showing zero snaps in both phases rules him out; anything less keeps
    the value unknown.
    """
    if line.unknown.get(TWO_POINT_RETURNS) != "UNATTRIBUTED_TEAM_EVENT" or snap is None:
        return line
    defense, special = _float(snap.get("defense_snaps")), _float(snap.get("st_snaps"))
    if defense != 0 or special != 0:
        return line
    values = dict(line.line.values) | {TWO_POINT_RETURNS: Decimal(0)}
    unknown = {k: v for k, v in line.unknown.items() if k != TWO_POINT_RETURNS}
    sources = dict(line.sources) | {
        TWO_POINT_RETURNS: line.sources[TWO_POINT_RETURNS]
        + "-snap_counts:no_defense_or_special_teams_snap(R-061)"
    }
    return replace(
        line, line=StatLine(scope=line.line.scope, values=values), sources=sources, unknown=unknown
    )


def rule_metrics(rules: RuleSet) -> list[str]:
    """The canonical metrics a rule set scores, once each, in rule order."""
    return list(dict.fromkeys(str(getattr(rule, "stat", "")) for rule in rules.rules))


def targets(
    rows: SeasonRows,
    rules: Mapping[str, RuleSet],
    labels: Sequence[Participation],
) -> list[Target]:
    """FFA lines and points for every player-game and D/ST team-game of the season's completed
    games that have play-by-play.

    Every player who played (a snap) without a statistics row gets an all-zero line, whatever
    his listed position: nflverse lists only players with a recorded statistic, and ESPN scored
    all 1,464 such played-weeks in 2025 and 2026 at zero (slice 1 verification). Which players
    the Model projects is decided later, not by this table.
    """
    plays: dict[str, list[Row]] = defaultdict(list)
    for play in rows.plays:
        plays[str(play["game_id"])].append(play)
    # A completed game without play-by-play has unknown scoring events, so it gets no targets.
    games = {g: game for g, game in _games(rows).items() if plays.get(g)}
    events: dict[str, GameEvents] = {g: game_events(plays[g]) for g in games}
    snaps = _snaps(rows)
    athlete_metrics, defense_metrics = (
        rule_metrics(rules["athlete"]),
        rule_metrics(rules["defense"]),
    )
    out: list[Target] = []

    def athlete(
        row: Row, game: _Game, basis: Basis, position: str | None, game_position: str | None
    ) -> None:
        gsis, team = str(row["player_id"]), str(row["team"])
        snap = snaps.get((game.game_id, gsis))
        line = athlete_line(row, events[game.game_id], athlete_metrics)
        if basis == "snaps_without_statistics":
            sources = dict(line.sources)
            for metric in ATHLETE_COLUMNS:
                if metric in sources:
                    sources[metric] = NO_STATISTICS_SOURCE
            line = replace(line, sources=sources)
        line = rule_out_two_point_returns(line, snap)
        points, refusal, parts = _scored(line, rules["athlete"])
        out.append(
            Target(
                role="athlete",
                season=rows.season,
                week=game.week,
                season_type=game.season_type,
                game_id=game.game_id,
                team=team,
                opponent=game.opponent(team),
                player_id=gsis,
                position=position,
                game_position=game_position
                if game_position is not None
                else (str(snap["position"]) if snap is not None else None),
                basis=basis,
                line=line,
                points=points,
                refusal=refusal,
                contributions=parts,
            )
        )

    recorded = set()
    for row in rows.players:
        game = games.get(str(row["game_id"]))
        if game is None or not row.get("player_id"):
            continue
        recorded.add((game.game_id, str(row["player_id"])))
        athlete(row, game, "statistics", row.get("position"), None)
    for label in labels:
        key = (label.game_id, label.player_id)
        if (
            label.label != "played"
            or label.evidence != "snap_counts"
            or key in recorded
            or label.game_id not in games
        ):
            continue
        zero = {"player_id": label.player_id, "team": label.team} | dict.fromkeys(STAT_COLUMNS, 0)
        athlete(zero, games[label.game_id], "snaps_without_statistics", None, label.position)

    team_rows = {(str(r["team"]), str(r["game_id"])): r for r in rows.teams}
    for game in games.values():
        for team in (game.home, game.away):
            opponent = game.opponent(team)
            own, theirs = (
                team_rows.get((team, game.game_id)),
                team_rows.get((opponent, game.game_id)),
            )
            if own is None or theirs is None:
                continue
            allowed = game.away_score if team == game.home else game.home_score
            line = defense_line(team, own, theirs, allowed, events[game.game_id], defense_metrics)
            points, refusal, parts = _scored(line, rules["defense"])
            out.append(
                Target(
                    role="defense",
                    season=rows.season,
                    week=game.week,
                    season_type=game.season_type,
                    game_id=game.game_id,
                    team=team,
                    opponent=opponent,
                    player_id=None,
                    position="D/ST",
                    game_position=None,
                    basis="team_statistics",
                    line=line,
                    points=points,
                    refusal=refusal,
                    contributions=parts,
                )
            )
    return out
