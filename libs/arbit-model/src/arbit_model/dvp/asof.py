"""What a DvP forecast may know at its cutoff, kept apart from what it is scored against (§2.2, §5).

- **Cutoffs.** `PREWEEK` (the default) is the first scheduled kickoff of the target game's NFL
  week, so a Thursday result never reaches a Sunday forecast. `PER_GAME` is the target game's own
  kickoff, a separate, explicitly versioned experiment in which earlier results that week count.
- **Features** (`FeatureView`) are observation rows whose FFA actuals were available by the
  cutoff. A game in progress, unfinished or canceled has no row, so it never counts.
- **Labels** (`LabelView`) are the target games' actual FFA rows. They meet forecasts only in
  `evaluation_join`, after the forecasts are frozen, one to one on immutable keys.
- **Priors** come only from observed FFA actuals in a feature view (T38).
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

import polars as pl

from arbit_model.dvp.observations import VALID
from arbit_model.dvp.provenance import LineageError, SourceType

LABEL_COLUMNS = frozenset({"points", "points_partial", "status"})
KEYS = ("game_id", "offense", "position")


class Cutoff(StrEnum):
    PREWEEK = "pre_first_game_of_nfl_week"
    PER_GAME = "per_game"


def cutoffs(schedule_games: pl.DataFrame, mode: Cutoff) -> pl.DataFrame:
    """Each scheduled game's forecast cutoff under the mode (game_id, cutoff)."""
    if mode is Cutoff.PER_GAME:
        return schedule_games.select("game_id", pl.col("kickoff").alias("cutoff"))
    first = pl.col("kickoff").min().over("season", "week")
    return schedule_games.select("game_id", first.alias("cutoff"))


@dataclass(frozen=True)
class FeatureView:
    cutoff: datetime
    mode: Cutoff
    frame: pl.DataFrame


@dataclass(frozen=True)
class LabelView:
    frame: pl.DataFrame


@dataclass(frozen=True)
class FrozenForecasts:
    frozen_at: datetime
    frame: pl.DataFrame  # KEYS, feature_as_of and forecast columns; never a label column


def features_as_of(rows: pl.DataFrame, cutoff: datetime, mode: Cutoff) -> FeatureView:
    """Observation rows available by the cutoff, stamped with it as `feature_as_of`."""
    known = rows.filter(pl.col("available_at") <= cutoff)
    late = known.filter(pl.col("kickoff") >= cutoff)
    if late.height:
        raise LineageError("FEATURE_AFTER_CUTOFF", f"{late.height} rows kicked off after {cutoff}")
    return FeatureView(cutoff, mode, known.with_columns(pl.lit(cutoff).alias("feature_as_of")))


def labels_for(rows: pl.DataFrame, game_ids: Sequence[str]) -> LabelView:
    """The target games' actual FFA rows, the evaluation labels."""
    return LabelView(rows.filter(pl.col("game_id").is_in(list(game_ids))))


def evaluation_join(forecasts: FrozenForecasts, labels: LabelView) -> pl.DataFrame:
    """Forecasts beside their labels, only once frozen and only one to one (T20, T36)."""
    leaked = LABEL_COLUMNS & set(forecasts.frame.columns)
    if leaked:
        raise LineageError("LABEL_IN_FORECAST", ", ".join(sorted(leaked)))
    if forecasts.frame.get_column("feature_as_of").max() > forecasts.frozen_at:  # type: ignore[operator]
        raise LineageError("FORECAST_NOT_FROZEN", "a feature is newer than the freeze")
    for name, frame in (("forecasts", forecasts.frame), ("labels", labels.frame)):
        if frame.select(KEYS).is_duplicated().any():
            raise LineageError("DUPLICATE_KEY", name)
    target = labels.frame.select(*KEYS, "kickoff", "points", "status")
    joined = forecasts.frame.join(target, on=list(KEYS), how="inner")
    if joined.height != forecasts.frame.height or joined.height != target.height:
        raise LineageError("UNMATCHED_ROWS", f"{forecasts.frame.height} vs {target.height}")
    if (joined.get_column("feature_as_of") > joined.get_column("kickoff")).any():
        raise LineageError("FEATURE_AFTER_KICKOFF", "a forecast used data after its game began")
    return joined


def league_prior(view: FeatureView, position: str) -> float | None:
    """Mean FFA points per team-game at the position over the view's valid observed rows."""
    rows = view.frame.filter(pl.col("position") == position)
    foreign = rows.filter(
        (pl.col("source_type") != SourceType.FFA_ACTUAL_FINAL.value)
        | (pl.col("observed_or_generated") != "observed")
    )
    if foreign.height:
        raise LineageError("PRIOR_FROM_NON_ACTUAL", f"{foreign.height} rows")
    valid = rows.filter(pl.col("status") == VALID).get_column("points")
    return float(valid.mean()) if valid.len() else None  # type: ignore[arg-type]
