"""FFA stat lines from nflverse weekly statistics and play-by-play. No fantasy arithmetic here.

Each canonical metric (the names `arbit_data.espn.scoring_mapping` gives ESPN's categories) is
built from named nflverse columns or a stated play-by-play rule, and the line is scored by
`arbit_core.scoring.score` under the stored FFA rules. Definitions were settled against ESPN's raw
statistics for every 2025 and 2026 player-week ESPN serves; see
docs/research/nflverse-ffa-scoring-2026-11-09.md. A metric the source cannot supply is `None`
with a reason, never zero, so the scorer refuses the line instead of under-counting it.
"""

from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

from arbit_core.rules import StatLine

ADAPTER_VERSION = "nflverse-ffa-stat-lines-v1"

# Columns summed into one metric, from the weekly player table (`stats_player_week_<season>`).
ATHLETE_COLUMNS: dict[str, tuple[str, ...]] = {
    "passing.yards": ("passing_yards",),
    "passing.touchdowns": ("passing_tds",),
    "passing.two_point_conversions": ("passing_2pt_conversions",),
    "passing.interceptions": ("passing_interceptions",),
    "rushing.yards": ("rushing_yards",),
    "rushing.touchdowns": ("rushing_tds",),
    "rushing.two_point_conversions": ("rushing_2pt_conversions",),
    "receiving.yards": ("receiving_yards",),
    "receiving.touchdowns": ("receiving_tds",),
    "receiving.two_point_conversions": ("receiving_2pt_conversions",),
    "receiving.receptions": ("receptions",),
    # Sack, rush, reception and return fumbles lost together, as ESPN counts them.
    "misc.fumbles_lost": ("fumbles_lost_total",),
    "misc.fumble_recovery_touchdowns": ("fumble_recovery_tds",),
    "kicking.field_goals_0_39": ("fg_made_0_19", "fg_made_20_29", "fg_made_30_39"),
    "kicking.field_goals_40_49": ("fg_made_40_49",),
    "kicking.field_goals_50_59": ("fg_made_50_59",),
    "kicking.field_goals_60_plus": ("fg_made_60_",),
    # ESPN's missed field goals include blocked attempts; nflverse keeps them apart.
    "kicking.field_goals_missed": ("fg_missed", "fg_blocked"),
    "kicking.extra_points_made": ("pat_made",),
}

# Play-by-play columns `game_events` reads.
PLAY_COLUMNS = (
    "game_id",
    "posteam",
    "defteam",
    "play_type",
    "touchdown",
    "td_team",
    "td_player_id",
    "interception",
    "punt_blocked",
    "field_goal_result",
    "extra_point_result",
    "kickoff_attempt",
    "punt_attempt",
    "extra_point_attempt",
    "two_point_attempt",
    "defensive_two_point_conv",
    "defensive_extra_point_conv",
    "posteam_score",
    "defteam_score",
    "posteam_score_post",
    "defteam_score_post",
    "fumble",
    "fumbled_1_team",
    "fumbled_2_team",
    "fumble_recovery_1_team",
    "fumble_recovery_2_team",
)

TouchdownKind = Literal[
    "kickoff", "punt", "blocked", "interception", "fumble", "own_fumble_recovery", "offense"
]

# Play-by-play touchdown kinds that FFA scores as return touchdowns.
RETURN_METRICS: dict[str, TouchdownKind] = {
    "returns.kickoff_touchdowns": "kickoff",
    "returns.punt_touchdowns": "punt",
    "returns.blocked_kick_touchdowns": "blocked",
    "returns.interception_touchdowns": "interception",
    "returns.fumble_touchdowns": "fumble",
}

# Team-level scoring events that play-by-play does not credit to a player.
TEAM_EVENT_METRICS = ("returns.two_point_returns", "misc.one_point_safeties")

# A D/ST line carries no offensive or kicking statistics; ESPN's were zero in every observed week.
DEFENSE_ZERO = tuple(ATHLETE_COLUMNS)

DEFENSE_METRICS = (
    "defense.points_allowed",
    "defense.yards_allowed",
    "defense.sacks",
    "defense.interceptions",
    "defense.fumbles_recovered",
    "defense.blocked_kicks",
    "defense.safeties",
    *RETURN_METRICS,
    *TEAM_EVENT_METRICS,
)

Unknown = Literal[
    "COLUMN_ABSENT",
    "VALUE_NULL",
    "VALUE_INVALID",
    "UNATTRIBUTED_TEAM_EVENT",
    "UNVERIFIED_SCORING_EVENT",
]
Credit = Literal["player", "none", "unverified"]


@dataclass(frozen=True)
class SourcedStatLine:
    line: StatLine
    sources: dict[str, str]
    unknown: dict[str, Unknown] = field(default_factory=dict)
    version: str = ADAPTER_VERSION


@dataclass(frozen=True)
class Touchdown:
    team: str
    kind: TouchdownKind
    # Counts toward the scoring team's D/ST (not when its offense scored).
    dst: bool
    # Points ESPN leaves out of the other team's D/ST points allowed.
    excluded_from_points_allowed: bool
    credit: Credit


@dataclass(frozen=True)
class GameEvents:
    """Scoring events from one game's play-by-play."""

    player_touchdowns: Counter[tuple[str, TouchdownKind]]
    team_touchdowns: Counter[tuple[str, TouchdownKind]]
    # Touchdowns of a credited kind whose scorer is not named, by scoring team.
    unattributed: frozenset[tuple[str, TouchdownKind]]
    # Scorers whose individual credit ESPN's treatment of the play leaves unsettled.
    unverified: frozenset[tuple[str, TouchdownKind]]
    # Opponent points ESPN leaves out of a team's points allowed, by the team scored against.
    excluded_points: Counter[str]
    safeties: Counter[str]
    one_point_safeties: Counter[str]
    two_point_returns: Counter[str]
    # A team's recoveries of opponent fumbles made by its offense after a turnover.
    offense_fumble_recoveries: Counter[str]


def _flag(value: Any) -> bool:
    return value is not None and value == value and float(value) == 1


def _kick(play: Mapping[str, Any]) -> Literal["kickoff", "punt"] | None:
    if play.get("play_type") == "kickoff" or _flag(play.get("kickoff_attempt")):
        return "kickoff"
    if play.get("play_type") == "punt" or _flag(play.get("punt_attempt")):
        return "punt"
    return None


def _kicking_team(play: Mapping[str, Any]) -> Any:
    # nflverse gives a kickoff to the receiving team and a punt to the punting team.
    return play.get("defteam") if _kick(play) == "kickoff" else play.get("posteam")


def _blocked(play: Mapping[str, Any]) -> bool:
    return (
        _flag(play.get("punt_blocked"))
        or play.get("field_goal_result") == "blocked"
        or play.get("extra_point_result") == "blocked"
    )


def _fumbling_team(play: Mapping[str, Any]) -> Any:
    """The team that lost the ball last on the play, if anyone fumbled."""
    if not _flag(play.get("fumble")):
        return None
    return play.get("fumbled_2_team") or play.get("fumbled_1_team")


def classify(play: Mapping[str, Any]) -> Touchdown:
    """ESPN's category for a touchdown, from the scorer and the kind of play.

    Observed against ESPN (research note): a muffed punt the kicking team recovers is a punt return
    TD for its D/ST; a kickoff the kicking team recovers in the end zone is a fumble return TD for
    its D/ST and no individual return TD; an offense that recovers the defense's fumble after a
    turnover scores an individual fumble return TD that is not its D/ST's; points allowed leave
    out only touchdowns the defense scores against the offense.
    """
    scorer = str(play.get("td_team"))
    defense = scorer == play.get("defteam")
    if _blocked(play) and defense:
        return Touchdown(scorer, "blocked", True, False, "player")
    kick = _kick(play)
    if kick is not None:
        if scorer == _kicking_team(play):
            if kick == "kickoff":
                return Touchdown(scorer, "fumble", True, False, "none")
            return Touchdown(scorer, "punt", True, False, "unverified")
        return Touchdown(scorer, kick, True, False, "player")
    if _flag(play.get("interception")) and defense:
        return Touchdown(scorer, "interception", True, True, "player")
    lost_by = _fumbling_team(play)
    if defense:
        return Touchdown(scorer, "fumble", True, True, "player")
    if lost_by is not None and lost_by != scorer:
        return Touchdown(scorer, "fumble", False, False, "player")
    if lost_by is not None:
        return Touchdown(scorer, "own_fumble_recovery", False, False, "none")
    return Touchdown(scorer, "offense", False, False, "none")


def _score_delta(play: Mapping[str, Any], side: str) -> int | None:
    before, after = play.get(f"{side}_score"), play.get(f"{side}_score_post")
    if before is None or after is None or before != before or after != after:
        return None
    return int(after) - int(before)


def offense_recoveries(play: Mapping[str, Any]) -> int:
    """Opponent fumbles the offense recovered after a turnover, slot by slot.

    nflverse pairs `fumbled_<k>_team` with `fumble_recovery_<k>_team`. Kicks, field goals and
    extra points are special teams plays, whose recoveries belong to the D/ST.
    """
    offense = play.get("posteam")
    special = _kick(play) is not None or play.get("play_type") in ("field_goal", "extra_point")
    if special or not offense or not _flag(play.get("fumble")):
        return 0
    return sum(
        1
        for k in (1, 2)
        if play.get(f"fumble_recovery_{k}_team") == offense
        and play.get(f"fumbled_{k}_team") not in (None, offense)
    )


def game_events(plays: Iterable[Mapping[str, Any]]) -> GameEvents:
    player_tds: Counter[tuple[str, TouchdownKind]] = Counter()
    team_tds: Counter[tuple[str, TouchdownKind]] = Counter()
    unattributed: set[tuple[str, TouchdownKind]] = set()
    unverified: set[tuple[str, TouchdownKind]] = set()
    excluded: Counter[str] = Counter()
    safeties: Counter[str] = Counter()
    one_point: Counter[str] = Counter()
    two_point_returns: Counter[str] = Counter()
    recoveries: Counter[str] = Counter()
    for play in plays:
        sides = {play.get("posteam"), play.get("defteam")} - {None}
        if _flag(play.get("touchdown")) and play.get("td_team"):
            touchdown = classify(play)
            if touchdown.dst:
                team_tds[(touchdown.team, touchdown.kind)] += 1
            if touchdown.excluded_from_points_allowed:
                for victim in sides - {touchdown.team}:
                    excluded[str(victim)] += 6
            scorer = play.get("td_player_id")
            if touchdown.credit == "player" and touchdown.kind != "offense":
                if scorer:
                    player_tds[(str(scorer), touchdown.kind)] += 1
                else:
                    unattributed.add((touchdown.team, touchdown.kind))
            elif touchdown.credit == "unverified" and scorer:
                unverified.add((str(scorer), touchdown.kind))
        if recovered := offense_recoveries(play):
            recoveries[str(play["posteam"])] += recovered
        try_play = _flag(play.get("extra_point_attempt")) or _flag(play.get("two_point_attempt"))
        for side in ("posteam", "defteam"):
            team = play.get(side)
            delta = _score_delta(play, side)
            if not team or delta is None:
                continue
            if delta == 2 and not try_play and not _flag(play.get("touchdown")):
                safeties[str(team)] += 1
                # Only a safety against the offense; one on a kick counts against the D/ST.
                if _kick(play) is None:
                    for victim in sides - {team}:
                        excluded[str(victim)] += 2
            elif delta == 1 and try_play and side == "defteam":
                one_point[str(team)] += 1
        if _flag(play.get("defensive_two_point_conv")) or _flag(
            play.get("defensive_extra_point_conv")
        ):
            if play.get("defteam"):
                two_point_returns[str(play["defteam"])] += 1
    return GameEvents(
        player_tds,
        team_tds,
        frozenset(unattributed),
        frozenset(unverified),
        excluded,
        safeties,
        one_point,
        two_point_returns,
        recoveries,
    )


def _number(row: Mapping[str, Any], columns: tuple[str, ...]) -> Decimal | Unknown:
    total = Decimal(0)
    for column in columns:
        if column not in row:
            return "COLUMN_ABSENT"
        value = row[column]
        if value is None or value != value:
            return "VALUE_NULL"
        try:
            number = Decimal(str(value))
        except InvalidOperation:
            return "VALUE_INVALID"
        if not number.is_finite():
            return "VALUE_INVALID"
        total += number
    return total


class _Builder:
    def __init__(self, metrics: Iterable[str], known: Iterable[str]) -> None:
        self.metrics = set(metrics)
        unmapped = self.metrics - set(known)
        if unmapped:
            raise ValueError("UNMAPPED_METRIC: " + ", ".join(sorted(unmapped)))
        self.values: dict[str, Decimal | None] = {}
        self.sources: dict[str, str] = {}
        self.unknown: dict[str, Unknown] = {}

    def set(self, metric: str, value: Decimal | Unknown, source: str) -> None:
        if metric not in self.metrics:
            return
        self.sources[metric] = source
        if isinstance(value, Decimal):
            self.values[metric] = value
        else:
            self.values[metric] = None
            self.unknown[metric] = value

    def build(self) -> SourcedStatLine:
        assert set(self.values) == self.metrics
        return SourcedStatLine(
            StatLine(scope="game", values=self.values), self.sources, self.unknown
        )


def athlete_line(
    row: Mapping[str, Any], events: GameEvents, metrics: Iterable[str]
) -> SourcedStatLine:
    """One player's game from the weekly player row and that game's play-by-play events."""
    builder = _Builder(metrics, [*ATHLETE_COLUMNS, *RETURN_METRICS, *TEAM_EVENT_METRICS])
    player, team = str(row.get("player_id") or ""), str(row.get("team") or "")
    for metric, columns in ATHLETE_COLUMNS.items():
        value = _number(row, columns)
        source = "stats_player." + "+".join(columns)
        if metric == "misc.fumble_recovery_touchdowns" and isinstance(value, Decimal):
            # nflverse counts every fumble recovered for a TD; ESPN scores an opponent's fumble
            # recovered for a TD as a fumble return TD instead.
            value -= events.player_touchdowns[(player, "fumble")]
            source += "-play_by_play.opponent_fumble_tds"
            if value < 0:
                value = "VALUE_INVALID"
        builder.set(metric, value, source)
    for metric, kind in RETURN_METRICS.items():
        credited: Decimal | Unknown
        if (team, kind) in events.unattributed:
            credited = "UNATTRIBUTED_TEAM_EVENT"
        elif (player, kind) in events.unverified:
            credited = "UNVERIFIED_SCORING_EVENT"
        else:
            credited = Decimal(events.player_touchdowns[(player, kind)])
        builder.set(metric, credited, f"play_by_play.td_player_id:{kind}")
    # Play-by-play names no player for these; only the scoring team's players are uncertain.
    for metric, counts in (
        ("returns.two_point_returns", events.two_point_returns),
        ("misc.one_point_safeties", events.one_point_safeties),
    ):
        builder.set(
            metric,
            "UNATTRIBUTED_TEAM_EVENT" if counts[team] else Decimal(0),
            "play_by_play.team_event",
        )
    return builder.build()


def defense_line(
    team: str,
    own: Mapping[str, Any],
    opponent: Mapping[str, Any],
    opponent_score: int,
    events: GameEvents,
    metrics: Iterable[str],
) -> SourcedStatLine:
    """A team defense/special teams game from both weekly team rows and play-by-play."""
    builder = _Builder(metrics, [*DEFENSE_METRICS, *DEFENSE_ZERO])
    for metric in DEFENSE_ZERO:
        builder.set(metric, Decimal(0), "policy:dst-has-no-offensive-statistics")
    # A one-point safety against this team is unobserved, so its treatment is not assumed.
    unverified = any(count for scorer, count in events.one_point_safeties.items() if scorer != team)
    builder.set(
        "defense.points_allowed",
        "UNVERIFIED_SCORING_EVENT"
        if unverified
        else Decimal(opponent_score - events.excluded_points[team]),
        "schedules.opponent_score-play_by_play.points_scored_against_offense",
    )
    yards = _number(opponent, ("passing_yards", "rushing_yards", "sack_yards_lost"))
    builder.set(
        "defense.yards_allowed", yards, "stats_team(opponent).passing+rushing+sack_yards_lost"
    )
    builder.set(
        "defense.sacks",
        _number(opponent, ("sacks_suffered",)),
        "stats_team(opponent).sacks_suffered",
    )
    builder.set(
        "defense.interceptions",
        _number(own, ("def_interceptions",)),
        "stats_team.def_interceptions",
    )
    recovered = _number(own, ("fumble_recovery_opp",))
    if isinstance(recovered, Decimal):
        # Recoveries the offense makes after a turnover are not the D/ST's.
        recovered -= events.offense_fumble_recoveries[team]
        if recovered < 0:
            recovered = "VALUE_INVALID"
    builder.set(
        "defense.fumbles_recovered",
        recovered,
        "stats_team.fumble_recovery_opp-play_by_play.offense_recoveries",
    )
    builder.set(
        "defense.blocked_kicks",
        _number(own, ("def_fg_blocks", "def_punt_blocks", "def_pat_blocks")),
        "stats_team.def_fg_blocks+def_punt_blocks+def_pat_blocks",
    )
    builder.set("defense.safeties", Decimal(events.safeties[team]), "play_by_play.score_delta")
    builder.set(
        "misc.one_point_safeties",
        Decimal(events.one_point_safeties[team]),
        "play_by_play.score_delta_on_try",
    )
    builder.set(
        "returns.two_point_returns",
        Decimal(events.two_point_returns[team]),
        "play_by_play.defensive_two_point_conv+defensive_extra_point_conv",
    )
    for metric, kind in RETURN_METRICS.items():
        builder.set(
            metric, Decimal(events.team_touchdowns[(team, kind)]), f"play_by_play.td_team:{kind}"
        )
    return builder.build()
