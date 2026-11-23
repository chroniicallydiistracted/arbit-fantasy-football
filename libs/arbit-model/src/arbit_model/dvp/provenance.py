"""Source lineage for the DvP research: an allowlist that fails closed (spec §2.1, §3; T30-T33, T37).

Every table the DvP pipeline reads is admitted here first. A source must be on the allowlist, name
its ancestry and, for FFA actuals, carry the league's scoring hash. Every column it holds must be
known: Arbit's FFA target tables by their adapter's fixed schema, nflverse tables by the field
catalog (`arbit_model.fields`). Excluded catalog columns (betting lines, generic fantasy points)
are dropped and recorded; an unknown column stops the pipeline. Admission follows lineage, not
column names, so a provider's projected points cannot enter renamed as, say, `opponent_expected`.
"""

import ast
import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

import polars as pl

from arbit_model.fields import classify


class SourceType(StrEnum):
    FFA_ACTUAL_FINAL = "FFA_ACTUAL_FINAL"
    REALIZED_NFL_STAT = "REALIZED_NFL_STAT"
    SCHEDULE = "SCHEDULE"
    ARBIT_MODEL_OUTPUT = "ARBIT_MODEL_OUTPUT"
    EXTERNAL_FANTASY_PROJECTION_FORBIDDEN = "EXTERNAL_FANTASY_PROJECTION_FORBIDDEN"


# Types that may feed features or labels. Model outputs are outputs only (spec §2.1).
INPUT_TYPES = frozenset(
    {SourceType.FFA_ACTUAL_FINAL, SourceType.REALIZED_NFL_STAT, SourceType.SCHEDULE}
)


class LineageError(ValueError):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code


# The FFA target tables (format arbit-ffa-targets-v1, adapter nflverse-ffa-stat-lines-v1).
TARGET_META = (
    "season",
    "week",
    "season_type",
    "game_id",
    "team",
    "opponent",
    "player_id",
    "position",
    "game_position",
    "basis",
    "participation",
    "points",
    "refusal",
)
TARGET_DETAIL = ("unknown", "source_overrides", "contributions")
ATHLETE_STATS = (
    "passing.yards",
    "passing.touchdowns",
    "passing.two_point_conversions",
    "passing.interceptions",
    "rushing.yards",
    "rushing.touchdowns",
    "rushing.two_point_conversions",
    "receiving.yards",
    "receiving.touchdowns",
    "receiving.two_point_conversions",
    "receiving.receptions",
    "misc.fumble_recovery_touchdowns",
    "misc.fumbles_lost",
    "kicking.field_goals_40_49",
    "kicking.field_goals_0_39",
    "kicking.field_goals_missed",
    "kicking.extra_points_made",
    "returns.blocked_kick_touchdowns",
    "returns.kickoff_touchdowns",
    "returns.punt_touchdowns",
    "returns.interception_touchdowns",
    "returns.fumble_touchdowns",
    "kicking.field_goals_50_59",
    "kicking.field_goals_60_plus",
    "returns.two_point_returns",
    "misc.one_point_safeties",
)
DEFENSE_STATS = (
    *ATHLETE_STATS,
    "defense.points_allowed",
    "defense.interceptions",
    "defense.fumbles_recovered",
    "defense.blocked_kicks",
    "defense.safeties",
    "defense.sacks",
    "defense.yards_allowed",
)


@dataclass(frozen=True)
class SourceSpec:
    source_id: str
    source_type: SourceType
    provider: str
    description: str
    used: tuple[str, ...]
    known: frozenset[str] = frozenset()  # fixed schema; empty when `family` classifies columns
    family: str | None = None  # nflverse family, classified by the field catalog
    scoring_role: str | None = None  # FFA actuals: the rule set whose hash must match
    values: Mapping[str, frozenset[str]] = field(default_factory=dict)  # allowed row values


SOURCES: Mapping[str, SourceSpec] = {
    spec.source_id: spec
    for spec in (
        SourceSpec(
            "ffa_targets.athlete",
            SourceType.FFA_ACTUAL_FINAL,
            "arbit",
            "Arbit's FFA points per player-game, scored by the shared scorer under the league's "
            "rules from nflverse final statistics (M3 slice 2)",
            used=(
                "season",
                "week",
                "season_type",
                "game_id",
                "team",
                "opponent",
                "player_id",
                "position",
                "basis",
                "points",
                "refusal",
            ),
            known=frozenset(TARGET_META + ATHLETE_STATS + TARGET_DETAIL),
            scoring_role="athlete",
            values={
                "basis": frozenset({"statistics", "snaps_without_statistics"}),
                "season_type": frozenset({"REG", "POST"}),
            },
        ),
        SourceSpec(
            "ffa_targets.defense",
            SourceType.FFA_ACTUAL_FINAL,
            "arbit",
            "Arbit's FFA points per D/ST team-game, scored by the shared scorer under the league's "
            "rules from nflverse final team statistics and play-by-play (M3 slice 2)",
            used=(
                "season",
                "week",
                "season_type",
                "game_id",
                "team",
                "opponent",
                "basis",
                "points",
                "refusal",
            ),
            known=frozenset(TARGET_META + DEFENSE_STATS + TARGET_DETAIL),
            scoring_role="defense",
            values={
                "basis": frozenset({"team_statistics"}),
                "season_type": frozenset({"REG", "POST"}),
            },
        ),
        SourceSpec(
            "nflverse.schedules",
            SourceType.SCHEDULE,
            "nflverse",
            "nflverse schedules: game keys, week, kickoff and final score",
            used=(
                "game_id",
                "season",
                "week",
                "game_type",
                "gameday",
                "gametime",
                "home_team",
                "away_team",
                "home_score",
                "away_score",
            ),
            family="schedules",
        ),
    )
}


@dataclass(frozen=True)
class Forbidden:
    """A fantasy projection, ranking or forecast that exists somewhere Arbit can reach."""

    source: str
    where: str
    reason: str
    guard: str
    decision: str


# Every provider projection or forecast known in Arbit, for the exclusion audit (T31).
FORBIDDEN: tuple[Forbidden, ...] = (
    Forbidden(
        "ESPN projected stat blocks (statSourceId 1)",
        "raw ESPN league and player responses Arbit stores",
        "ESPN's pregame fantasy projection",
        "ESPN readers keep statSourceId 0 (actuals) only; no DvP source reads ESPN",
        "OWN-061",
    ),
    Forbidden(
        "ESPN draft probabilities and analyst ranks",
        "nflverse misc/espn_draft_player_probs, misc/espn_draft_position_probs",
        "another provider's projections",
        "field catalog rule espn-draft-projections (excluded); not a DvP source",
        "OWN-061",
    ),
    Forbidden(
        "ffopportunity expected fantasy points",
        "nflverse ff_opportunity",
        "another provider's fantasy model and points",
        "field catalog rule ffopportunity (excluded); not a DvP source",
        "OWN-061",
    ),
    Forbidden(
        "DynastyProcess and FantasyPros values, rankings and projections",
        "nflverse dynastyprocess",
        "provider rankings and projections",
        "field catalog rule dynastyprocess-values (excluded); not a DvP source",
        "OWN-061",
    ),
    Forbidden(
        "Generic fantasy points (fantasy_points, fantasy_points_ppr)",
        "nflverse stats_player and other weekly statistics",
        "actual points under upstream scoring, not FFA's rules: never a substitute for FFA scoring",
        "field catalog rule generic-fantasy-points (excluded); dropped on admission",
        "OWN-061",
    ),
    Forbidden(
        "Sleeper projections and rankings",
        "arbit_data.sleeper (supplemental directory reads)",
        "another provider's projections",
        "not a DvP source; arbit_model.dvp imports nothing from arbit_data.sleeper",
        "OWN-061",
    ),
    Forbidden(
        "Betting lines (spread, total, moneyline, vegas win probability)",
        "nflverse schedules and play-by-play",
        "a market forecast, gated to the Q-014 study",
        "field catalog rule betting-lines (excluded); dropped on admission",
        "OWN-067",
    ),
)


@dataclass(frozen=True)
class Admission:
    source_id: str
    source_type: SourceType
    provider: str
    ancestry: str
    scoring_hash: str | None
    used: tuple[str, ...]
    dropped: Mapping[str, str]  # column -> catalog rule that excludes it
    rows: int
    frame: pl.DataFrame

    def record(self) -> dict[str, Any]:
        return {
            "sourceId": self.source_id,
            "sourceType": self.source_type.value,
            "provider": self.provider,
            "ancestry": self.ancestry,
            "scoringHash": self.scoring_hash,
            "columnsUsed": list(self.used),
            "columnsDropped": dict(sorted(self.dropped.items())),
            "rows": self.rows,
        }


def admit(
    frame: pl.DataFrame,
    source_id: str,
    *,
    ancestry: str | None,
    scoring_hash: str | None = None,
    expected_scoring: Mapping[str, str] | None = None,
    schema: Sequence[str] | None = None,
) -> Admission:
    """The frame's permitted columns, or a LineageError naming why it cannot enter.

    `schema` is the source's full column list when the frame holds only some of its columns (a
    Parquet file read for the used columns); every listed column must still be known."""
    spec = SOURCES.get(source_id)
    if spec is None:
        raise LineageError("UNKNOWN_SOURCE", source_id)
    if spec.source_type not in INPUT_TYPES:
        raise LineageError("FORBIDDEN_SOURCE_TYPE", f"{source_id}: {spec.source_type}")
    if not ancestry:
        raise LineageError("MISSING_ANCESTRY", source_id)
    if spec.scoring_role is not None:
        expected = (expected_scoring or {}).get(spec.scoring_role)
        if not expected or scoring_hash != expected:
            raise LineageError(
                "SCORING_HASH_MISMATCH",
                f"{source_id}: {scoring_hash} is not the configured {spec.scoring_role} rules",
            )
    dropped: dict[str, str] = {}
    for column in list(schema) if schema is not None else frame.columns:
        if spec.family is None:
            if column not in spec.known:
                raise LineageError("UNKNOWN_COLUMN", f"{source_id}.{column}")
            continue
        rule = classify(spec.family, column)
        if rule is None:
            raise LineageError("UNKNOWN_COLUMN", f"{source_id}.{column}")
        if rule.use == "excluded":
            dropped[column] = rule.id
    for column in spec.used:
        if column not in frame.columns:
            raise LineageError("MISSING_COLUMN", f"{source_id}.{column}")
        if column in dropped:
            raise LineageError("EXCLUDED_COLUMN_USED", f"{source_id}.{column}")
    for column, allowed in spec.values.items():
        seen = set(frame.get_column(column).drop_nulls().unique().to_list())
        if not seen <= allowed:
            raise LineageError("UNKNOWN_VALUE", f"{source_id}.{column}: {sorted(seen - allowed)}")
    return Admission(
        source_id=source_id,
        source_type=spec.source_type,
        provider=spec.provider,
        ancestry=ancestry,
        scoring_hash=scoring_hash,
        used=spec.used,
        dropped=dropped,
        rows=frame.height,
        frame=frame.select(spec.used),
    )


def ancestry_hash(admissions: list[Admission]) -> str:
    """One digest of every admitted source's lineage record, for experiment results."""
    body = json.dumps(sorted((a.record() for a in admissions), key=str), sort_keys=True)
    return hashlib.sha256(body.encode()).hexdigest()


# Field-name tokens of provider projections, rankings and generic fantasy points (T31). This module
# names them to forbid them, so the code scan leaves it out.
PROJECTION_TOKENS = re.compile(
    r"projected_|_projected|projected\w*points|fantasy_points|statsourceid|appliedprojected"
    r"|ff_?opportunity|dynastyprocess|fantasypros|expected_fantasy|\becr\b",
    re.IGNORECASE,
)
FORBIDDEN_IMPORTS = ("arbit_data.espn", "arbit_data.sleeper")


def scan_code(path: Path) -> list[str]:
    """Projection field tokens and provider-reader imports in one source file."""
    text = path.read_text()
    found = [
        f"{path}:{number}: token {match.group(0)}"
        for number, line in enumerate(text.splitlines(), 1)
        for match in PROJECTION_TOKENS.finditer(line)
    ]
    for node in ast.walk(ast.parse(text)):
        if isinstance(node, ast.Import):
            modules = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            modules = [node.module or ""]
        else:
            continue
        found += [
            f"{path}:{node.lineno}: imports {module}"
            for module in modules
            if module.startswith(FORBIDDEN_IMPORTS)
        ]
    return found
