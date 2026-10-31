"""Pure observed revision replay. No score deltas, source deletions or route inference."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from arbit_core.identity import require_aware

from arbit_data.live.contracts import LivePlay


@dataclass(frozen=True)
class PlaySnapshot:
    event_id: str
    observed_at: datetime
    plays: tuple[LivePlay, ...]
    play_observed_at: tuple[tuple[str, datetime], ...] = ()

    def __post_init__(self) -> None:
        require_aware(self.observed_at)
        ids = {p.provider_id for p in self.plays}
        if (
            len(self.plays) > 6000
            or any(p.event_id != self.event_id for p in self.plays)
            or len(ids) != len(self.plays)
        ):
            raise ValueError("INVALID_PLAY_SNAPSHOT")
        if self.play_observed_at:
            if (
                len(self.play_observed_at) != len(ids)
                or {key for key, _ in self.play_observed_at} != ids
            ):
                raise ValueError("INVALID_PLAY_OBSERVATION_TIMES")
            for _, at in self.play_observed_at:
                require_aware(at)
                if at > self.observed_at:
                    raise ValueError("PLAY_OBSERVATION_AFTER_SNAPSHOT")

    def evidence_times(self) -> dict[str, datetime]:
        return (
            dict(self.play_observed_at)
            if self.play_observed_at
            else {p.provider_id: self.observed_at for p in self.plays}
        )


@dataclass(frozen=True)
class ReplayResult:
    snapshot: PlaySnapshot
    changes: tuple[dict[str, Any], ...]
    ignored_older: bool = False
    limitations: tuple[str, ...] = (
        "A missing play is not a source deletion. No fantasy arithmetic is performed.",
    )


def _ordered(plays: dict[str, LivePlay]) -> tuple[LivePlay, ...]:
    return tuple(
        sorted(
            plays.values(),
            key=lambda p: (p.sequence is None, Decimal(p.sequence or "0"), p.provider_id),
        )
    )


def merge_observations(previous: PlaySnapshot | None, current: PlaySnapshot) -> ReplayResult:
    if previous is not None and previous.event_id != current.event_id:
        raise ValueError("EVENT_SCOPE_MISMATCH")
    if previous is not None and current.observed_at < previous.observed_at:
        return ReplayResult(previous, (), True)
    effective = {p.provider_id: p for p in previous.plays} if previous else {}
    effective_times = previous.evidence_times() if previous else {}
    current_times = current.evidence_times()
    changes = []
    for play in current.plays:
        old = effective.get(play.provider_id)
        at = current_times[play.provider_id]
        if old is not None:
            old_at = effective_times[play.provider_id]
            if at < old_at:
                continue
            if old == play:
                effective_times[play.provider_id] = max(old_at, at)
                continue
            if at == old_at:
                raise ValueError("AMBIGUOUS_OBSERVATION")
            if (
                old.modified_at
                and play.modified_at
                and datetime.fromisoformat(play.modified_at.replace("Z", "+00:00"))
                < datetime.fromisoformat(old.modified_at.replace("Z", "+00:00"))
            ):
                continue
        effective[play.provider_id] = play
        effective_times[play.provider_id] = at
        changes.append(
            {
                "play_id": play.provider_id,
                "type": "cancelled"
                if play.cancelled
                else "introduced"
                if old is None
                else "revised",
            }
        )
    snapshot = PlaySnapshot(
        current.event_id,
        current.observed_at,
        _ordered(effective),
        tuple(sorted(effective_times.items())),
    )
    return ReplayResult(snapshot, tuple(changes))
