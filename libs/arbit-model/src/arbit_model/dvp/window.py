"""The prospective window's completion gate (owner directive AUD-01c; config/dvp/prospective-amendment-1.json).

A week counts toward the 2026 confirmation only when:
- its forecasts were archived before the week's cutoff;
- the archive still matches its ledger entry;
- a commitment to those exact bytes reached an external, independently timestamped record
  before the cutoff;
- every scheduled game of the week is final, and every archived forecast has its label
  (valid, or invalid for a recorded reason).

The window can confirm (CONFIRMED / NOT_CONFIRMED under the frozen rules) only when every
predeclared week qualifies. A missed week makes the window INCOMPLETE_WINDOW: it stays
descriptive. Any integrity conflict makes it BLOCKED.

Pure functions: the harness gathers the facts (ledger entries, file checks, publication records,
schedule, labelled forecasts) and these decide.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

import polars as pl

# Archive states of one week.
PENDING = "PENDING"  # no archive yet, cutoff not passed
PROSPECTIVE = "PROSPECTIVE"  # archived, verified and externally committed before the cutoff
MISSED = "MISSED"  # the cutoff passed without a qualifying prospective archive
BLOCKED = "BLOCKED"  # conflicting entries or an archive that no longer matches its ledger
# Label states of one week.
AWAITING_GAMES = "AWAITING_GAMES"
LABELS_INCOMPLETE = "LABELS_INCOMPLETE"
LABELLED = "LABELLED"
# Window states.
INTERIM = "INTERIM"
INCOMPLETE_WINDOW = "INCOMPLETE_WINDOW"
COMPLETE = "COMPLETE"  # every predeclared week qualifies: the frozen rules may label it
# Labels of evaluations that never confirm.
RETROSPECTIVE = "RETROSPECTIVE"
REHEARSAL = "REHEARSAL"

PER_GAME_TARGETS = 12  # two teams x QB, RB, WR, TE, K, D/ST


def _time(value: Any) -> datetime | None:
    if value is None or isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))


@dataclass
class WeekArchive:
    """What the harness found for one week."""

    week: int
    cutoff: datetime
    entries: Sequence[Mapping[str, Any]]  # ledger entries for the week
    files_match: Mapping[str, bool] = field(default_factory=dict)  # folder -> every file matches
    publications: Sequence[Mapping[str, Any]] = field(default_factory=list)  # verified records


def archive_state(found: WeekArchive, now: datetime) -> dict[str, Any]:
    """The week's archive state with every reason, never silently PROSPECTIVE."""
    entries = list(found.entries)
    prospective = [e for e in entries if e.get("classification") == PROSPECTIVE]
    missed = [e for e in entries if e.get("classification") == MISSED]
    retrospective = [e for e in entries if e.get("classification") == RETROSPECTIVE]
    reasons: list[str] = []
    evidence: dict[str, Any] = {"retrospectiveArchives": len(retrospective)}
    if len(prospective) > 1:
        reasons.append("more than one prospective archive for the week")
    if prospective and missed:
        reasons.append("the week is recorded both archived and missed")
    if reasons:
        return {"status": BLOCKED, "reasons": reasons, "evidence": evidence}
    if prospective:
        entry = prospective[0]
        folder = str(entry.get("folder"))
        if not found.files_match.get(folder, False):
            return {
                "status": BLOCKED,
                "reasons": [f"{folder} no longer matches its ledger entry"],
                "evidence": evidence,
            }
        generated = _time(entry.get("generatedAt"))
        archived = _time(entry.get("archivedAt") or entry.get("recordedAt"))
        evidence |= {
            "folder": folder,
            "generatedAt": str(generated),
            "archivedAt": str(archived),
            "cutoff": found.cutoff.isoformat(),
        }
        if generated is None or generated >= found.cutoff:
            reasons.append("generated at or after the cutoff")
        if archived is None or archived >= found.cutoff:
            reasons.append("not durably archived before the cutoff")
        published = [
            p
            for p in found.publications
            if p.get("ledgerEntrySha256") == entry.get("entrySha256") and p.get("verified")
        ]
        before = [
            p
            for p in published
            if (_time(p.get("externalTimestamp")) or found.cutoff) < found.cutoff
        ]
        evidence["externalCommitments"] = [
            {k: p.get(k) for k in ("kind", "ref", "commit", "externalTimestamp")} for p in published
        ]
        if not before:
            reasons.append("no verified external commitment before the cutoff")
        if reasons:
            # Archived but not provably before the cutoff: kept as evidence, never prospective.
            status = MISSED if now >= found.cutoff else PENDING
            return {"status": status, "reasons": reasons, "evidence": evidence}
        return {"status": PROSPECTIVE, "reasons": [], "evidence": evidence}
    if missed:
        return {
            "status": MISSED,
            "reasons": [str(m.get("reason", "recorded missed")) for m in missed],
            "evidence": evidence,
        }
    if now >= found.cutoff:
        return {
            "status": MISSED,
            "reasons": ["the cutoff passed with no archive"],
            "evidence": evidence,
        }
    return {"status": PENDING, "reasons": ["the cutoff has not passed"], "evidence": evidence}


def label_state(
    week: int,
    schedule: pl.DataFrame,
    labelled: pl.DataFrame | None,
    now: datetime,
    grace: timedelta,
) -> dict[str, Any]:
    """Every scheduled game of the week against the archived forecasts and their labels.

    `schedule` holds the week's games (game_id, kickoff, available_at, status). `labelled` holds
    the week's archived forecasts with `label_status` (attach_labels), or None without an archive.
    A game still without a result after `grace` is recorded as postponed or canceled and doesn't
    hold the week open; any other unfinished game does."""
    games = schedule.filter(pl.col("week") == week)
    if games.is_empty():
        return {"status": AWAITING_GAMES, "reasons": ["no scheduled games"], "games": 0}
    completed = games.filter(pl.col("status") == "completed")
    unfinished = games.filter(pl.col("status") != "completed")
    exceptional = unfinished.filter(pl.col("kickoff") + grace <= now)
    awaiting = unfinished.filter(pl.col("kickoff") + grace > now)
    unavailable = completed.filter(pl.col("available_at") > now)
    reasons: list[str] = []
    detail: dict[str, Any] = {
        "games": games.height,
        "completed": completed.height,
        "awaitingResult": sorted(awaiting.get_column("game_id").to_list()),
        "postponedOrCanceled": sorted(exceptional.get_column("game_id").to_list()),
        "resultsNotYetAvailable": sorted(unavailable.get_column("game_id").to_list()),
    }
    if awaiting.height:
        reasons.append(f"{awaiting.height} game(s) not final")
    if unavailable.height:
        reasons.append(f"{unavailable.height} final game(s) not yet available under the rule")
    if labelled is None:
        return {
            "status": AWAITING_GAMES if reasons else LABELS_INCOMPLETE,
            "reasons": [*reasons, "no archived forecasts"],
            **detail,
        }
    week_rows = labelled.filter(pl.col("week") == week)
    final_ids = set(completed.get_column("game_id").to_list())
    scheduled_ids = set(games.get_column("game_id").to_list())
    counts = week_rows.group_by("game_id").len()
    per_game = dict(zip(counts.get_column("game_id"), counts.get_column("len"), strict=True))
    unknown = sorted(set(per_game) - scheduled_ids)
    without = sorted(final_ids - set(per_game))
    short = sorted(g for g in final_ids & set(per_game) if per_game[g] != PER_GAME_TARGETS)
    on_final = week_rows.filter(pl.col("game_id").is_in(list(final_ids)))
    status_counts = on_final.group_by("label_status").len()
    labels = dict(
        zip(status_counts.get_column("label_status"), status_counts.get_column("len"), strict=True)
    )
    missing = int(labels.get("missing", 0))
    invalid = {k: int(v) for k, v in labels.items() if k not in ("valid", "missing")}
    detail |= {
        "forecastRows": week_rows.height,
        "labels": dict(sorted((str(k), int(v)) for k, v in labels.items())),
        "invalidLabels": dict(sorted(invalid.items())),
        "forecastsForUnscheduledGames": unknown,
        "finalGamesWithoutForecasts": without,
        "gamesWithWrongTargetCount": short,
    }
    if unknown:
        reasons.append("forecasts for games not on the schedule")
    if without:
        reasons.append(f"{len(without)} final game(s) without archived forecasts")
    if short:
        reasons.append(f"{len(short)} game(s) without exactly {PER_GAME_TARGETS} targets")
    if missing:
        reasons.append(f"{missing} forecast(s) on final games without a label")
    if awaiting.height or unavailable.height:
        status = AWAITING_GAMES
    elif reasons:
        status = LABELS_INCOMPLETE
    else:
        status = LABELLED
    return {"status": status, "reasons": reasons, **detail}


def window_state(
    weeks: Sequence[int],
    declared: Sequence[int],
    archives: Mapping[int, Mapping[str, Any]],
    labels: Mapping[int, Mapping[str, Any]],
) -> dict[str, Any]:
    """The window's state. Only COMPLETE lets the frozen rules assign CONFIRMED or NOT_CONFIRMED."""
    reasons: list[str] = []
    blocked = [w for w in weeks if archives[w]["status"] == BLOCKED]
    if blocked:
        return {
            "status": BLOCKED,
            "confirmationAllowed": False,
            "reasons": [f"week {w}: {'; '.join(archives[w]['reasons'])}" for w in blocked],
        }
    if list(weeks) != list(declared):
        return {
            "status": INTERIM,
            "confirmationAllowed": False,
            "reasons": ["a subset of the predeclared window: descriptive only"],
        }
    missed = [w for w in weeks if archives[w]["status"] == MISSED]
    if missed:
        return {
            "status": INCOMPLETE_WINDOW,
            "confirmationAllowed": False,
            "reasons": [f"week {w} missed: {'; '.join(archives[w]['reasons'])}" for w in missed],
        }
    for w in weeks:
        if archives[w]["status"] != PROSPECTIVE:
            reasons.append(f"week {w}: archive {archives[w]['status']}")
        if labels[w]["status"] != LABELLED:
            reasons.append(f"week {w}: labels {labels[w]['status']}")
    if reasons:
        return {"status": INTERIM, "confirmationAllowed": False, "reasons": reasons}
    return {"status": COMPLETE, "confirmationAllowed": True, "reasons": []}


# Readiness of each earlier game before a week is forecast (AUD-01b; amendment readiness.perGame).
ELIGIBLE_VERIFIED = "ELIGIBLE_VERIFIED"
RETRIEVED_INVALID = "RETRIEVED_INVALID"
AWAITING_RESULT = "AWAITING_RESULT"
POSTPONED_OR_CANCELED = "POSTPONED_OR_CANCELED"
NOT_YET_AVAILABLE = "NOT_YET_AVAILABLE"
SOURCE_NOT_YET_PUBLISHED = "SOURCE_NOT_YET_PUBLISHED"
PUBLISHED_NOT_RETRIEVED = "PUBLISHED_NOT_RETRIEVED"
DATA_INTEGRITY_FAILURE = "DATA_INTEGRITY_FAILURE"
READY_STATES = (ELIGIBLE_VERIFIED, RETRIEVED_INVALID, POSTPONED_OR_CANCELED)
GAME_LENGTH = timedelta(hours=4)  # results can't exist before kickoff + this


def game_readiness(
    schedule: pl.DataFrame,
    observations: pl.DataFrame,
    season: int,
    week: int,
    now: datetime,
    grace: timedelta,
    held_revision: datetime | None,
    catalog_revision: datetime | None,
) -> tuple[bool, dict[str, Any]]:
    """Is every game before `week` complete in the data the frozen method would read?

    `held_revision` is when nflverse last revised the player-statistics file Arbit imported;
    `catalog_revision` is the newest revision Arbit's catalog has seen. A game's 12 observation
    cells must all be present; a cell invalid for a recorded reason (a refused line) does not
    block, as in the frozen data rules."""
    earlier = schedule.filter((pl.col("season") == season) & (pl.col("week") < week))
    cells = (
        observations.filter(pl.col("season") == season)
        .group_by("game_id")
        .agg(
            pl.len().alias("cells"),
            (pl.col("status") == "valid").sum().alias("valid"),
            pl.struct("game_id", "offense", "position").is_duplicated().any().alias("dup"),
        )
    )
    found = {r["game_id"]: r for r in cells.iter_rows(named=True)}
    states: dict[str, str] = {}
    for game in earlier.iter_rows(named=True):
        gid, kickoff = game["game_id"], game["kickoff"]
        row = found.get(gid)
        if game["status"] != "completed":
            states[gid] = AWAITING_RESULT if kickoff + grace > now else POSTPONED_OR_CANCELED
        elif game["available_at"] > now:
            states[gid] = NOT_YET_AVAILABLE
        elif row is not None and row["cells"] == PER_GAME_TARGETS and not row["dup"]:
            states[gid] = ELIGIBLE_VERIFIED if row["valid"] == row["cells"] else RETRIEVED_INVALID
        elif held_revision is None or held_revision < kickoff + GAME_LENGTH:
            newer = catalog_revision is not None and (
                held_revision is None or catalog_revision > held_revision
            )
            states[gid] = PUBLISHED_NOT_RETRIEVED if newer else SOURCE_NOT_YET_PUBLISHED
        else:
            states[gid] = DATA_INTEGRITY_FAILURE
    by_state: dict[str, list[str]] = {}
    for gid, state in sorted(states.items()):
        by_state.setdefault(state, []).append(gid)
    counts = {k: len(v) for k, v in sorted(by_state.items())}
    blocking = {k: v for k, v in by_state.items() if k not in READY_STATES}
    detail = {
        "earlierGames": earlier.height,
        "states": counts,
        "blocking": blocking,
        "postponedOrCanceled": by_state.get(POSTPONED_OR_CANCELED, []),
        "retrievedInvalid": by_state.get(RETRIEVED_INVALID, []),
        "heldStatisticsRevision": None if held_revision is None else held_revision.isoformat(),
        "catalogStatisticsRevision": None
        if catalog_revision is None
        else catalog_revision.isoformat(),
    }
    return not blocking, detail
