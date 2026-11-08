"""Fit a play's natural phases to its real snap-to-whistle time (OWN-051, OWN-052).

A template plans its play as phases: the mesh, the path to the hole, the drive through contact,
the dead ball before the whistle, and so on. Each has a least, natural and most length at
natural speeds. Given the NFL's real time, every phase with room grows by the same share of its
room, or shrinks by the same share toward its least, so the play fills the real time with more
football rather than slower movement. Time the phases can't absorb is reported: `unfilled` when
the real play was longer than every phase's most, `over` when it was shorter than every least.
"""

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class Phase:
    name: str
    least: float
    natural: float
    most: float

    def __post_init__(self) -> None:
        if not 0 <= self.least <= self.natural <= self.most:
            raise ValueError(f"phase {self.name}: need 0 <= least <= natural <= most")


@dataclass(frozen=True)
class Fitted:
    seconds: dict[str, float]
    unfilled: float = 0.0  # real time beyond every phase's most
    over: float = 0.0  # how far even the least plan runs past the real whistle


def fit(phases: Sequence[Phase], budget: float | None) -> Fitted:
    """Each phase's length for a play of `budget` seconds from snap to whistle (None: natural)."""
    natural = sum(p.natural for p in phases)
    if budget is None:
        return Fitted({p.name: p.natural for p in phases})
    if budget >= natural:
        room = sum(p.most - p.natural for p in phases)
        share = min(1.0, (budget - natural) / room) if room > 0 else 0.0
        seconds = {p.name: p.natural + share * (p.most - p.natural) for p in phases}
        return Fitted(seconds, unfilled=max(0.0, budget - natural - room))
    room = sum(p.natural - p.least for p in phases)
    share = min(1.0, (natural - budget) / room) if room > 0 else 0.0
    seconds = {p.name: p.natural - share * (p.natural - p.least) for p in phases}
    return Fitted(seconds, over=max(0.0, natural - budget - room))
