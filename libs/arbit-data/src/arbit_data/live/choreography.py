"""Play scripts from play facts (automation slice 2): passes, interceptions, sacks and runs.

`choreograph(facts, seed, names)` turns one play's `PlayFacts` into a `PlayScript`: each named
player's timeline of poses and positions, where the ball is at every moment, the lines and the
caption. Only the players ESPN names appear (OWN-021, OWN-032). Positions are in field yards: x from
the offense's own goal line, so the offense always attacks toward 100; z from the near sideline; y up.

The play ends exactly on ESPN's spot. What the feed doesn't say, such as where between the hashes
the ball was snapped, how a receiver lined up or where a tackler came from, is chosen by a
generator seeded by play ID and revision, so the same play always looks the same and a corrected
play changes only when its facts do. The ball names the hand or chest that holds it and the hands
that catch it; the renderer resolves those from each frame, so a catch always lands in the hands.

Movement stays natural (owner review, 2026-11-03): every player runs at one speed of his own for
the whole play, and timing follows from the routes instead of stretching anyone's stride. A
receiver on a short route gets to his spot, settles and comes back to the ball; on a deep route
he runs through the catch. The quarterback's drop fits the throw, and while he waits he works his
feet in the pocket. Anyone waiting sets with a small side step instead of freezing. When a tackler
needs longer to get there, the carrier weaves rather than slowing down.
"""

import copy
import hashlib
import math
import random
import re
from collections.abc import Callable, Mapping
from contextvars import ContextVar
from typing import Literal

from arbit_data.live import alignment as A
from arbit_data.live.contracts import LiveModel
from arbit_data.live.play_facts import PenaltyFacts, PlayFacts
from arbit_data.live.timing import Phase
from arbit_data.live.timing import fit as fit_phases

FIELD_WIDTH = 160 / 3
HASHES = (23.58, 29.75)  # NFL hash marks, 70 ft 9 in from each sideline
SNAP = 0.6  # seconds of set before the snap
TOP_SPEED = 9.2  # yards a second, about 19 mph
CYCLES = frozenset({"RUN", "DROP", "BACKPEDAL", "OFF_RUN"})
OFFICIAL_JOG = 5.5  # yards a second: an official moving to his spot
BACKPEDAL = 5.0  # yards a second: a defensive back's backpedal, without the ball
BULLET = 32.0  # yards a second: the fastest a short pass flies (OWN-037)
STANCE, IDLE = "stance_1", "idle_1"  # waiting for the play, and done with it (OWN-037)
UNDER = 1.25  # yards behind the line a quarterback under center takes the snap, behind the center
# Each team's center, long snapper and quarterback: (ESPN ID, name as the text writes it).
Units = Mapping[str, Mapping[str, tuple[str, str]]]
# Poses that carry a body's momentum through contact or a catch, and how fast they may travel.
MOMENTUM = {
    # A kicker's last steps into the ball and a punter's step into the drop carry his approach.
    "kick_plant": 5.0,
    "kick_swing": 5.5,
    "kick_strike": 3.0,
    "punt_drop": 5.0,
    "punt_strike": 5.5,
    "hit": 6.0,
    "stumble": 6.0,
    "lunge": 8.0,
    "wrap": 6.0,
    "drive": 4.0,
    "tackle_dive": 8.0,
    "fall_30": 4.0,
    "fall_60": 4.0,
    "hit_back": 6.0,
    "fall_back_30": 4.0,
    "fall_back_60": 4.0,
    "catch_reach_e": 9.0,
    "catch_reach": 9.0,
    "catch_high_e": 9.0,
    "catch_high": 9.0,
    "catch_secure": 9.5,
    "dive_catch": 8.0,
    "take": 9.5,  # the back takes the handoff in stride
    "handoff_give": 3.0,
    "handoff_follow": 3.0,
    "slide": 7.0,
}
STILL = 1.5  # yards a second: the most a standing pose may drift
SLOWEST_RUN = 5.5  # yards a second: below this the run cycle reads as slow motion
LONGEST_STILL = 0.6  # seconds a standing pose may hold without a step, except before the snap
DEEPEST = 20.0  # yards past the line a defender may line up, as deep as a safety
LABEL = "Re-creation from play-by-play"
TEMPLATES = frozenset(
    {
        "pass",
        "spike",
        "interception",
        "sack",
        "run",
        "scramble",
        "kneel",
        "punt",
        "kickoff",
        "field_goal",
    }
)
# Shapes the play facts leave without a template that slice 3 draws anyway, from their facts.
INCIDENTS = frozenset({"fumble", "penalty"})
_SPEEDS = {  # each player's own pace, drawn once per play
    "receiver": (7.4, 8.4),
    "rusher": (7.0, 8.2),
    "defense": (7.0, 8.2),
    "quarterback": (6.2, 7.2),
}


class Segment(LiveModel):
    start: float
    end: float
    pose: str
    x0: float
    z0: float
    x1: float
    z1: float
    facing: Literal["right", "left"] | None = None  # None: the actor's own facing


class Actor(LiveModel):
    key: str
    espn_id: str | None  # None: named only in the text, such as "Center-C.Stoll" on a punt
    role: str
    side: Literal["offense", "defense", "official"]  # officials throw the flags (OWN-037)
    label: str | None = None
    # The player's depth chart position, such as "RG" or "WOLB", when it's known (OWN-036).
    position: str | None = None
    facing: Literal["right", "left"]
    segments: tuple[Segment, ...]


class BallEnd(LiveModel):
    """Where a flight starts or ends: an actor's hand, chest or catching hands, or a point."""

    actor: str | None = None
    hold: Literal["hand", "chest", "hands"] | None = None
    point: tuple[float, float, float] | None = None


class BallSegment(LiveModel):
    start: float
    end: float
    state: Literal["rest", "held", "flight"]
    actor: str | None = None
    at: tuple[float, float, float] | None = None
    origin: BallEnd | None = None
    target: BallEnd | None = None
    spin: Literal["spiral", "tumble", "upright", "flat"] = "spiral"


class Line(LiveModel):
    kind: Literal["scrimmage", "to_gain"]
    x: float


class Prop(LiveModel):
    """Something else on the field. A flag is thrown at `start` by the nearest official, who
    isn't drawn, from `origin`, and lands at `at` at `land`, where it stays."""

    kind: Literal["flag"]
    start: float
    land: float
    origin: tuple[float, float, float]
    at: tuple[float, float, float]


class PlayScript(LiveModel):
    version: Literal[1] = 1
    event_id: str
    provider_id: str
    seed: str
    template: str
    duration: float
    # When the play is over: its last movement, before the closing hold. The board shows the
    # play's result from here (slice 5).
    whistle: float
    offense: str | None
    defense: str | None
    actors: tuple[Actor, ...]
    ball: tuple[BallSegment, ...]
    lines: tuple[Line, ...]
    caption: str
    props: tuple[Prop, ...] = ()
    label: str = LABEL
    note: str | None = None


class _Track:
    """One actor's timeline, built forward in time like the hand-written review plays."""

    def __init__(self, x: float, z: float, speed: float):
        self.t, self.x, self.z, self.speed = 0.0, x, z, speed
        self.segments: list[Segment] = []

    def move(
        self, pose: str, seconds: float, x: float, z: float, facing: str | None = None
    ) -> "_Track":
        if seconds > 1e-6:
            self.segments.append(
                Segment(
                    start=round(self.t, 4),
                    end=round(self.t + seconds, 4),
                    pose=pose,
                    x0=round(self.x, 3),
                    z0=round(self.z, 3),
                    x1=round(x, 3),
                    z1=round(z, 3),
                    facing=facing,  # type: ignore[arg-type]
                )
            )
            self.t += seconds
        self.x, self.z = x, z
        return self

    def hold(self, pose: str, seconds: float, facing: str | None = None) -> "_Track":
        return self.move(pose, seconds, self.x, self.z, facing)

    def run(self, x: float, z: float, facing: str | None = None) -> "_Track":
        """Run to (x, z) at this actor's own pace."""
        distance = math.hypot(x - self.x, z - self.z)
        return self.move("RUN", distance / self.speed, x, z, facing) if distance > 0.05 else self

    def run_by(
        self,
        x: float,
        z: float,
        arrive: float,
        side: int,
        facing: str | None = None,
        wait_first: bool = True,
    ) -> None:
        """Run to (x, z) at this actor's pace and get there at `arrive`. With time to spare the
        path bends out to `side`, up to a third longer, and any time still left is spent set in
        place: first for a defender, who then breaks at full speed; last for a ball carrier, who
        shouldn't stand holding the ball."""
        distance = math.hypot(x - self.x, z - self.z)
        window = arrive - self.t
        if distance < 0.05:
            settle(self, arrive, facing=facing)
            return
        path = min(max(distance, window * self.speed), distance * 1.35)
        spare = window - path / self.speed
        if wait_first and spare > 0:
            settle(self, self.t + spare, facing=facing)
        if path > distance * 1.05:
            self.run(*_waypoint((self.x, self.z), (x, z), path, side), facing)
        self.run(x, z, facing)
        settle(self, arrive, facing=facing)


def settle(
    track: _Track, until: float, style: str = "set", facing: str | None = None, climb: bool = True
) -> None:
    """Hold a position until `until` without freezing. A quarterback works his feet in the pocket
    and, if `climb`, steps up a little; anyone else sets with a small side step and back. Each step
    moves in proportion to its length, so even a clipped last step stays a step."""
    if style == "pocket":
        frames, step, rise, sway = (
            ("drop_b", "drop_c", "drop_b", "drop_a"),
            0.22,
            0.1 if climb else 0.0,
            0.16,
        )
    elif style == "idle":  # done with the play: weight shifts, hands at his sides
        frames, step, rise, sway = (IDLE, "idle_2", IDLE, "idle_2"), 0.4, 0.0, 0.15
    else:  # waiting for the play: weight shifts in his stance, never the quarterback's frames
        frames, step, rise, sway = (STANCE, "stance_2", STANCE, "stance_2"), 0.3, 0.0, 0.22
    base = track.z
    index = 0
    while track.t < until - 1e-3:
        seconds = min(step, until - track.t)
        share = seconds / step
        want = base + (0.0, sway, 0.0, -sway)[index % 4]
        z = track.z + max(-sway * share, min(sway * share, want - track.z))
        track.move(frames[index % 4], seconds, track.x + rise * share, z, facing)
        index += 1


def _waypoint(
    a: tuple[float, float], b: tuple[float, float], length: float, side: int
) -> tuple[float, float]:
    """The point off the straight line from a to b that makes a two-leg path `length` long."""
    distance = math.hypot(b[0] - a[0], b[1] - a[1])
    half = max(length, distance) / 2
    reach = math.sqrt(max(0.0, half * half - (distance / 2) ** 2))
    mx, mz = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
    nx, nz = (-(b[1] - a[1]) / distance, (b[0] - a[0]) / distance) if distance else (0.0, 1.0)
    z = mz + side * nz * reach
    if not 1.0 <= z <= FIELD_WIDTH - 1.0:  # bend the other way rather than off the field
        z = mz - side * nz * reach
    return mx + side * nx * reach, min(FIELD_WIDTH - 1.0, max(1.0, z))


# The real snap-to-whistle time of the play being choreographed, set by `choreograph` and
# `kicking.choreograph_try` for every play state they make.
REAL_SECONDS: ContextVar[float | None] = ContextVar("real_seconds", default=None)


class _Play:
    """Shared state while one play is choreographed."""

    def __init__(
        self,
        facts: PlayFacts,
        seed: str,
        names: Mapping[str, str],
        positions: Mapping[str, tuple[str, ...]] | None = None,
        units: "Units | None" = None,
    ):
        self.facts = facts
        self.seed = seed
        self.rng = random.Random(int.from_bytes(hashlib.sha256(seed.encode()).digest()[:8], "big"))
        self.los = float(facts.start or 0)
        self.end = float(facts.action_end if facts.action_end is not None else facts.end or 0)
        self.z = self.rng.uniform(*HASHES)
        self.actors: list[tuple[str, str | None, str, str, _Track, str]] = []
        self.ball: list[BallSegment] = []
        self.note: str | None = None
        self.catch: tuple[float, float, float] | None = None
        self.props: list[Prop] = []
        self.names = names
        self.positions = positions or {}
        self.units = units or {}
        # Fouls drawn in the play: its own penalties, or the one that wiped it out (OWN-037),
        # and where and when the contact came, for the flag.
        self.fouls = tuple(facts.penalties)
        self.contact: dict[str, tuple[float, float, float]] = {}
        self._context: A.Context | None = None
        self.text_names = _text_names(facts.text)
        self.labels: dict[str, str] = {}  # by actor key, for players named only in the text
        # The NFL's snap-to-whistle time, when known: templates fit their phases to it (OWN-052).
        self.budget = REAL_SECONDS.get()
        self.extra: dict[str, float] = {}  # seconds each flexible phase adds in this build
        self.timed = False  # built to the real time: the whistle is the real whistle
        self._made = (facts, seed, names, positions, units)

    def again(self) -> "_Play":
        """A fresh state for the same play, which draws the same random choices."""
        return _Play(*self._made)

    def ids(self, role: str) -> list[str]:
        return list(dict.fromkeys(p.espn_id for p in self.facts.players if p.role == role))

    def track(self, x: float, z: float, kind: str) -> _Track:
        return _Track(x, z, self.rng.uniform(*_SPEEDS[kind]))

    def add(
        self,
        key: str,
        espn_id: str | None,
        role: str,
        side: str,
        track: _Track,
        facing: str,
        label: str | None = None,
    ) -> _Track:
        self.actors.append((key, espn_id, role, side, track, facing))
        if label:
            self.labels[key] = label
        return track

    def position(self, espn_id: str | None, side: str | None = None) -> str | None:
        """His depth chart position: the one for `side` of the ball when given (None if he has
        none there), else his first."""
        codes = self.positions.get(espn_id or "", ())
        if side is not None:
            return A.pick(codes, side)
        return codes[0] if codes else None

    def unit(self, job: str, team: str | None = None) -> tuple[str, str] | None:
        """The offense's (or `team`'s) center, long snapper or quarterback, when known."""
        return self.units.get(team or self.facts.offense or "", {}).get(job)

    def entry(self, track: "_Track") -> tuple[str, str | None, str, str, "_Track", str]:
        return next(actor for actor in self.actors if actor[4] is track)

    def context(self) -> A.Context:
        """What the play says about the alignment: its kind, which side it goes, and the strong
        side, which is the tight end's: the offense's right unless a pass goes left to him."""
        if self._context is None:
            facts = self.facts
            template = facts.template or ""
            kind: Literal["pass", "run", "kick", "other"] = (
                "pass"
                if template in ("pass", "interception", "sack", "spike", "scramble")
                else "run"
                if template in ("run", "kneel")
                else "kick"
                if template in ("punt", "kickoff", "field_goal")
                else "other"
            )
            said = (facts.passing.side if facts.passing else None) or (
                facts.run.side if facts.run else None
            )
            side = -1 if said == "left" else 1 if said == "right" else 0
            tight_end_left = side < 0 and any(
                self.position(espn_id, "offense") == "TE" for espn_id in self.ids("receiver")
            )
            self._context = A.Context(
                los=self.los,
                ball_z=self.z,
                shotgun=bool(facts.shotgun),
                kind=kind,
                side=side,
                strong=-1 if tight_end_left else 1,
            )
        return self._context

    def side_of(self, key: str) -> str:
        return next(side for k, _, _, side, _, _ in self.actors if k == key)

    def flag(self, thrown: float, x: float, z: float) -> None:
        """A flag landing at (x, z), thrown by the nearest official (OWN-037): the one on that
        sideline for a foul within 15 yards of it, otherwise the umpire or back judge, a few
        yards off the foul in the middle of the field. He's drawn from his spot before the snap,
        jogs to where he throws from, reaches for the flag and throws it."""
        x = min(108.0, max(-8.0, x))
        z = min(FIELD_WIDTH - 0.5, max(0.5, z))
        if z < 15.0:
            origin = (x + self.rng.uniform(-4.0, 4.0), 2.0, -1.5)
            home = (self.los + self.rng.uniform(-1.0, 1.0), -1.5)  # on the line, off the sideline
        elif z > FIELD_WIDTH - 15.0:
            origin = (x + self.rng.uniform(-4.0, 4.0), 2.0, FIELD_WIDTH + 1.5)
            home = (self.los + self.rng.uniform(-1.0, 1.0), FIELD_WIDTH + 1.5)
        else:
            away = self.rng.choice((-1, 1)) * self.rng.uniform(5.0, 8.0)
            origin = (x + away, 2.0, z + self.rng.uniform(-4.0, 4.0))
            # The umpire behind the defensive front, or the back judge deep.
            home = (self.los + (6.5 if origin[0] < self.los + 12 else 20.0), self.z + away * 0.3)
        # Clear of everyone: a second official on the same line starts a few yards along it.
        taken = [
            (t.segments[0].x0, t.segments[0].z0) if t.segments else (t.x, t.z)
            for *_, t, _ in self.actors
        ]
        while any(math.hypot(home[0] - x0, home[1] - z0) < 1.5 for x0, z0 in taken):
            home = (home[0] + 3.0, home[1])
        # He can't move before the snap: he throws from as far as he gets by then.
        reach_at = thrown - 0.4
        far = math.hypot(origin[0] - home[0], origin[2] - home[1])
        leave = max(SNAP + 0.2, reach_at - far / OFFICIAL_JOG)
        spot = home
        if far > 1e-6 and reach_at > leave:
            share = min(1.0, OFFICIAL_JOG * (reach_at - leave) / far)
            spot = (
                home[0] + (origin[0] - home[0]) * share,
                home[1] + (origin[2] - home[1]) * share,
            )
        origin = (spot[0], 2.0, spot[1])
        land = thrown + 0.45 + math.hypot(x - origin[0], z - origin[2]) / 30.0
        self.props.append(
            Prop(
                kind="flag",
                start=round(thrown, 4),
                land=round(land, 4),
                origin=(round(origin[0], 3), origin[1], round(origin[2], 3)),
                at=(round(x, 3), 0.05, round(z, 3)),
            )
        )
        self._official(home, spot, leave, thrown)

    def _official(
        self, home: tuple[float, float], spot: tuple[float, float], leave: float, thrown: float
    ) -> None:
        index = sum(1 for _, _, role, *_ in self.actors if role == "official") + 1
        track = _Track(home[0], home[1], OFFICIAL_JOG)
        facing = "left" if spot[0] < home[0] else "right"
        self.add(f"official_{index}", None, "official", "official", track, facing)
        far = math.hypot(spot[0] - home[0], spot[1] - home[1])
        track.hold("off_idle", leave if far > 0.05 else max(0.05, thrown - 0.4))
        if far > 0.05:
            track.move("OFF_RUN", far / OFFICIAL_JOG, *spot)
        track.hold("off_reach", max(0.05, thrown - 0.1 - track.t)).hold("off_throw", 0.2)
        track.hold("off_follow", 0.4).hold("off_idle", 0.4)

    def find(self, key: str) -> _Track:
        return next(t for k, _, _, _, t, _ in self.actors if k == key)

    def hold_ball(self, actor: str, start: float, end: float = 1e9) -> None:
        self.ball.append(
            BallSegment(start=round(start, 4), end=round(end, 4), state="held", actor=actor)
        )

    def release(self, actor: str, at: float) -> None:
        """End the actor's open hold at `at`, when he throws or hands off."""
        for index, seg in enumerate(self.ball):
            if seg.state == "held" and seg.actor == actor and seg.end > at:
                self.ball[index] = seg.model_copy(update={"end": round(at, 4)})

    def fly(
        self, start: float, end: float, origin: BallEnd, target: BallEnd, spin: str = "spiral"
    ) -> None:
        self.ball.append(
            BallSegment(
                start=round(start, 4),
                end=round(end, 4),
                state="flight",
                origin=origin,
                target=target,
                spin=spin,  # type: ignore[arg-type]
            )
        )

    def rest(self, start: float, end: float, at: tuple[float, float, float]) -> None:
        if round(end, 4) - round(start, 4) > 1e-6:  # times are kept to 4 places
            point = (round(at[0], 3), round(at[1], 3), round(at[2], 3))
            self.ball.append(
                BallSegment(
                    start=round(start, 4), end=round(end, 4), state="rest", at=point, spin="flat"
                )
            )

    def lane(self, side: str | None) -> float:
        """Where across the field a pass to the offense's left, middle or right goes. The offense
        attacks toward 100, so its left is the near sideline (small z)."""
        if side == "left":
            return self.rng.uniform(6.0, 17.0)
        if side == "right":
            return self.rng.uniform(36.0, 47.0)
        return self.rng.uniform(21.0, 32.0)


def choreograph(
    facts: PlayFacts,
    seed: str,
    names: Mapping[str, str] | None = None,
    positions: Mapping[str, tuple[str, ...]] | None = None,
    units: Units | None = None,
    real_seconds: float | None = None,
) -> PlayScript | None:
    """A script for the play, or None when its facts have no template here or miss a fact.
    `names` gives display names by ESPN ID, from the rosters; the text fills in only a role that
    names exactly one player. Kicks, fumbles and penalties are drawn by `kicking` and `incidents`.
    `real_seconds` is the NFL's snap-to-whistle time, which the play is built to (OWN-052)."""
    token = REAL_SECONDS.set(real_seconds)
    try:
        return _choreograph(facts, seed, names, positions, units)
    finally:
        REAL_SECONDS.reset(token)


def _choreograph(
    facts: PlayFacts,
    seed: str,
    names: Mapping[str, str] | None,
    positions: Mapping[str, tuple[str, ...]] | None,
    units: Units | None,
) -> PlayScript | None:
    from arbit_data.live import incidents

    if facts.reason in ("trick_play", "lateral") or (
        facts.shape == "fumble" and " Lateral " in facts.text
    ):
        return incidents.partial(facts, seed, names or {}, positions or {}, units or {})
    if facts.shape in INCIDENTS and facts.reason in ("fumble", "no_play"):
        return incidents.choreograph(facts, seed, names or {}, positions or {}, units or {})
    if facts.template not in TEMPLATES or facts.missing or facts.start is None:
        return None
    built = _build(_Play(facts, seed, names or {}, positions, units))
    if built is None:
        return None
    incidents.flags(built)
    return _finish(built, caption=incidents.caption(built.facts))


def _build(play: _Play) -> _Play | None:
    """Draw the play with the template its facts name."""
    from arbit_data.live import kicking

    facts = play.facts
    if facts.template in ("punt", "kickoff", "field_goal"):
        return kicking.build(play)
    if facts.template == "kneel" or (facts.run and facts.run.style == "kneel"):
        return _kneel(play)
    if facts.template == "spike":
        return _spike(play)
    if facts.template == "pass" and facts.passing:
        return _pass(play)
    if facts.template == "interception":
        return _interception(play)
    if facts.template == "sack":
        return _sack(play)
    if facts.template in ("run", "scramble"):
        return _to_time(play, _run, _run_phases)
    return None


DEAD_BALL = Phase("dead", 0.4, 0.7, 1.5)  # from the end of the action to a natural whistle
HANDOFF_BY = SNAP + 0.9  # the run's handoff comes right after the snap (OWN-037)
SCRAMBLE_LOOK = 0.4  # seconds of a scrambler's look in the pocket that timing may take back
MOST_DRIVE = 2.5  # seconds a pile may last: a carrier driving through contact, tacklers on him
DRIVE_PACE = 1.6  # yards a second a pile moves


def _to_time(
    play: _Play,
    build: Callable[[_Play], _Play | None],
    flexible: Callable[[_Play], list[Phase]],
) -> _Play | None:
    """Build the play to its real snap-to-whistle time (OWN-052). The natural build fixes the
    action; the template's flexible phases and the dead ball share out the rest, and the play is
    built again from the same seed with them. A carry can absorb or add a little time around its
    tacklers, so any difference comes out of, or goes into, the phases that add directly to the
    end: the drive through contact first, then the path, then the mesh."""
    if play.budget is None:
        return build(play)

    def ends(built: _Play) -> float:
        """When the play is over as it will be drawn: with any flag thrown in it (OWN-038)."""
        from arbit_data.live import incidents

        if not any(not p.no_play for p in built.facts.penalties):
            return _moments(built)[1] - SNAP
        flagged = copy.deepcopy(built)
        incidents.flags(flagged)
        return _moments(flagged)[1] - SNAP

    natural = build(play.again())
    if natural is None:
        return None
    action = ends(natural)
    phases = [Phase("action", action, action, action), *flexible(play), DEAD_BALL]
    fitted = fit_phases(phases, play.budget)
    most = {p.name: p.most for p in phases}
    extra = {k: v for k, v in fitted.seconds.items() if k not in ("action", "dead")}
    built: _Play | None = None
    for _ in range(4):
        attempt = play.again()
        attempt.extra = dict(extra)
        built = build(attempt)
        if built is None:
            return None
        error = ends(built) + fitted.seconds["dead"] - play.budget
        if abs(error) < 0.05:
            break
        before = dict(extra)
        for name in ("drive", "path", "mesh"):
            if name in extra and abs(error) >= 0.05:
                changed = min(most[name], max(0.0, extra[name] - error))
                error -= extra[name] - changed
                extra[name] = changed
        if all(abs(extra[k] - before[k]) < 0.01 for k in extra):
            break
    assert built is not None
    built.timed = True
    play.__dict__.update(built.__dict__)  # callers keep the state they passed in
    return play


_PATH_ROOM = {"end": 1.5, "tackle": 1.2}  # seconds a back's path may bend, by the hole


def _run_phases(play: _Play) -> list[Phase]:
    """A run's flexible phases: a slower mesh or a longer look in the pocket, a path to the hole
    that bends wider, and the drive through contact when he's tackled."""
    facts = play.facts
    style = facts.run.style if facts.run else "run"
    gap = facts.run.gap if facts.run and facts.run.gap else ""
    tackled = not facts.touchdown and not facts.out_of_bounds
    if style == "scramble":
        # Shorter or longer in the pocket before he takes off.
        phases = [Phase("mesh", 0.0, SCRAMBLE_LOOK, SCRAMBLE_LOOK + 1.5)]
    elif style == "sneak":
        phases = []
    else:
        phases = [Phase("mesh", 0.0, 0.0, 0.3)]
        if play.end > play.los + 1:
            phases.append(Phase("path", 0.0, 0.0, _PATH_ROOM.get(gap, 1.0)))
    if tackled:
        phases.append(Phase("drive", 0.0, 0.0, MOST_DRIVE))
    return phases


# The quarterback -----------------------------------------------------------------------------


def _center(play: _Play) -> None:
    """The team's center over the ball (OWN-037): he snaps it and stays down in his stance."""
    unit = play.unit("center")
    on_ball = (*play.ids("passer"), *play.ids("receiver"), *play.ids("rusher"))
    if (
        unit is None
        or unit[0] in on_ball
        or any(espn_id == unit[0] for _, espn_id, *_ in play.actors)
    ):
        return
    track = play.add(
        "snapper",
        unit[0],
        "snapper",
        "offense",
        play.track(play.los - 0.3, play.z, "defense"),
        "right",
        play.names.get(unit[0]) or unit[1],
    )
    track.hold("snap_ready", SNAP).hold("snap_release", 0.35).hold("snap_ready", 0.3)


def _snap(
    play: _Play,
    key: str,
    espn_id: str | None,
    role: str,
    start_x: float,
    shotgun: bool,
    label: str | None = None,
) -> _Track:
    """A quarterback (or a back taking a direct snap) sets and takes the snap from the center."""
    _center(play)
    track = play.add(
        key, espn_id, role, "offense", play.track(start_x, play.z, "quarterback"), "right", label
    )
    play.rest(0.0, SNAP, (play.los, 0.15, play.z))
    if shotgun:
        track.hold("ready", SNAP + 0.3)
        play.fly(
            SNAP,
            SNAP + 0.3,
            BallEnd(point=(play.los, 0.3, play.z)),
            BallEnd(actor=key, hold="hand"),
        )
        play.hold_ball(key, SNAP + 0.3)
    else:
        track.hold("ready", SNAP)
        play.hold_ball(key, SNAP)
    return track


def _drop(play: _Play, track: _Track, steps: int) -> None:
    """A quick, three-step or five-step drop, at a natural pace."""
    shotgun = play.facts.shotgun
    depth = {1: 0.8, 3: 1.6, 5: 2.6}[steps] if shotgun else {1: 2.5, 3: 4.2, 5: 6.2}[steps]
    target = track.x - depth
    track.move("DROP", depth / play.rng.uniform(3.2, 3.8), target, track.z)


def _throw(track: _Track, release: float) -> None:
    """Pocket footwork until the throw, then the throw itself; the ball leaves at `release`."""
    settle(track, release - 0.55, "pocket")
    track.hold("drop_b", max(0.0, release - 0.4 - track.t))
    track.hold("throw_cock", 0.3).hold("throw_mid", 0.1)
    track.hold("throw_rel", 0.15).hold("throw_follow", 0.45).hold("stand", 0.3)


def _steps_for(air: float) -> int:
    return 1 if air < 4 else 3 if air < 15 else 5


# Pass templates -------------------------------------------------------------------------------


def _air(play: _Play) -> float:
    """Air yards: ESPN's (ENG-032) when it states them, else a draw from the measured range for
    the depth the text gives (short −4 to 13, deep 17 to 42)."""
    passing = play.facts.passing
    if passing and passing.air_yards is not None:
        return float(passing.air_yards)
    if passing and passing.depth == "deep":
        return play.rng.uniform(17.0, 38.0)
    return play.rng.uniform(-2.0, 12.0)


def _flight(play: _Play, x: float, z: float, from_x: float, air: float) -> float:
    """Seconds in the air: a thrown ball travels about 26 yards a second, a deep one about 22."""
    return 0.25 + math.hypot(x - from_x, z - play.z) / (22.0 if air >= 15 else 26.0)


def _pass(play: _Play) -> _Play | None:
    facts = play.facts
    passing = facts.passing
    assert passing is not None
    complete = passing.result == "complete"
    air = _air(play)
    gained = play.end - play.los
    if complete and passing.air_yards is None:
        air = min(air, gained)  # without yards after catch, the catch can't be past the tackle
    catch_x, catch_z = play.los + air, play.lane(passing.side)
    deep = air >= 18
    steps = _steps_for(air)
    qb = _snap(
        play,
        "passer",
        play.ids("passer")[0],
        "passer",
        play.los - (5.0 if facts.shotgun else UNDER),
        facts.shotgun,
    )
    _drop(play, qb, steps)
    earliest = qb.t + 0.55  # a beat set, then the throwing motion
    qb_x = qb.x
    receivers = play.ids("receiver")
    if not receivers:  # thrown away: he looks, then throws it out of bounds
        release = max(earliest, SNAP + play.rng.uniform(2.4, 3.2))
        _throw(qb, release)
        play.release("passer", release)
        out = (
            -1.5
            if passing.side == "left" or (passing.side is None and play.z < FIELD_WIDTH / 2)
            else FIELD_WIDTH + 1.5
        )
        landing = (play.los + play.rng.uniform(4.0, 10.0), 0.12, out)
        flight = _flight(play, landing[0], out, qb_x, 8.0)
        play.fly(
            release, release + flight, BallEnd(actor="passer", hold="hand"), BallEnd(point=landing)
        )
        play.rest(release + flight, 1e9, landing)
        return play
    # The receiver's route sets the timing. He releases off the line at his own pace.
    lateral = play.rng.uniform(0.0, 3.0) if deep else play.rng.uniform(2.0, 7.0)
    start_z = min(51.5, max(1.5, catch_z + play.rng.choice((-1, 1)) * lateral))
    start_x = min(play.los - 0.3, catch_x - 1.5) if air < 1 else play.los - 0.3
    # A tight end starts inline and a back in the backfield, on the side of the pass (OWN-036).
    kind = A.group(play.position(receivers[0], "offense"))
    toward = 1 if catch_z >= play.z else -1
    if kind == "OL":
        start_x, start_z = play.los - 0.3, play.z
    elif kind == "TE":
        start_x, start_z = play.los - 0.7, play.z + 4.2 * play.context().strong
    elif kind in ("RB", "FB"):
        depth = 4.5 if kind == "FB" else 5.0 if facts.shotgun else 7.0
        start_x, start_z = play.los - depth, play.z + 1.5 * toward
    elif kind == "WR":  # on the line, even for a catch behind it, and at least in the slot
        start_x = play.los - 0.5
        if abs(start_z - play.z) < 6.0:
            out = 1 if start_z > play.z else -1 if start_z < play.z else toward
            start_z = min(51.5, max(1.5, play.z + out * play.rng.uniform(6.0, 8.0)))
    start_x, start_z = _apart(play, None, start_x, start_z)
    receiver = play.add(
        "receiver",
        receivers[0],
        "receiver",
        "offense",
        play.track(start_x, start_z, "receiver"),
        "right",
    )
    # The defenders who covered him line up first. A cover man's spot decides how long the play
    # takes: if he needs longer to get there, the route runs longer, never the man faster.
    covers: list[tuple[_Track, float, float]] = []  # (track, gap, arrival after the catch)
    if not complete and play.ids("passDefender"):
        defender = play.add(
            "defender",
            play.ids("passDefender")[0],
            "passDefender",
            "defense",
            play.track(catch_x + 7.0, catch_z + 2.5, "defense"),
            "left",
        )
        _place(play, defender, catch_x + 0.9, catch_z + 0.5, earliest + 1.0, SNAP)
        covers.append((defender, 1.0, -0.2))
    for index, espn_id in enumerate(
        list(dict.fromkeys(play.ids("tackler") + play.ids("assistedBy")))[:2] if complete else []
    ):
        if A.group(play.position(espn_id, "defense")) not in ("LB", "CB", "NB", "S"):
            continue  # a lineman who makes the tackle comes from the rush, in the carry
        cover = play.add(
            f"tackler_{index + 1}",
            espn_id,
            "tackler" if index == 0 else "assistedBy",
            "defense",
            play.track(catch_x + 6.0, catch_z + 2.0, "defense"),
            "left",
        )
        _place(play, cover, catch_x + 2.0, catch_z, earliest + 1.0, SNAP)
        covers.append((cover, 2.0 + 1.5 * index, 0.15))
    coverage_foul = next(
        (f for f in (_foul(play, "holding"), _foul(play, "contact"), _foul(play, "dpi")) if f), None
    )
    flagged = next(iter(play.ids("penalized")), None)
    drawn = {espn_id for _, espn_id, *_ in play.actors}
    if complete and coverage_foul is not None and flagged and flagged not in drawn:
        marked = play.add(
            "penalized",
            flagged,
            "penalized",
            "defense",
            play.track(catch_x + 6.0, catch_z, "defense"),
            "left",
            play.names.get(flagged) or coverage_foul.player,
        )
        _place(play, marked, catch_x + 3.0, catch_z, earliest + 1.0, SNAP)
        covers.append((marked, 3.0, 0.15))
    needed = max(
        (
            SNAP + 0.2 + max(0.0, math.hypot(t.x - catch_x, t.z - catch_z) - gap) / t.speed - after
            for t, gap, after in covers
        ),
        default=0.0,
    )
    catch_t, release, flight = _route(
        play, receiver, (catch_x, catch_z), deep, air, qb_x, earliest, needed
    )
    play.catch = (catch_x, catch_z, catch_t)
    _throw(qb, release)
    play.release("passer", release)
    for cover, gap, after in covers if complete else []:
        # (An incomplete pass's defender covers in _incomplete.) A foul in the coverage is drawn
        # with the first cover man, or the penalized one (OWN-037).
        if _called_on(play, cover):
            _coverage_foul(play, cover, receiver, release, catch_t)
        _cover(play, cover, receiver, (catch_x, catch_z), gap, catch_t + after, stay=True)
    if not complete:
        return _incomplete(play, release, catch_t, catch_x, catch_z)
    play.fly(
        release,
        catch_t,
        BallEnd(actor="passer", hold="hand"),
        BallEnd(actor="receiver", hold="hands"),
    )
    play.hold_ball("receiver", catch_t)
    ahead = gained >= air + 0.5
    secured = catch_x + (receiver.speed * 0.2 if deep and ahead else 0.4 if ahead else 0.0)
    receiver.move("catch_secure", 0.2, min(secured, max(catch_x, play.end - 0.7)), catch_z)
    _carry(play, receiver, "receiver", catch_z, way=1)
    return play


def _route(
    play: _Play,
    receiver: _Track,
    catch: tuple[float, float],
    deep: bool,
    air: float,
    qb_x: float,
    earliest: float,
    not_before: float = 0.0,
) -> tuple[float, float, float]:
    """The receiver runs his route at his own pace and catches the ball as he gets there; the
    throw is timed to meet him (OWN-037). A short pass that the quarterback can't throw early
    enough flies faster and flatter, a bullet of up to 32 yards a second; failing that, and on
    every deep pass, which keeps its pace, the route runs longer. He is never slowed. Returns the
    catch, the release and the time in the air."""
    catch_x, catch_z = catch
    start_x, start_z = receiver.x, receiver.z
    reach = receiver.speed * 0.27
    across = math.hypot(catch_x - start_x, catch_z - start_z) or 1.0
    ux, uz = (catch_x - start_x) / across, (catch_z - start_z) / across
    before = (catch_x - ux * min(reach, across * 0.8), catch_z - uz * min(reach, across * 0.8))
    facing = "right" if ux >= -0.2 else "left"
    poses = (
        ("catch_high_e", "catch_high") if deep and air >= 20 else ("catch_reach_e", "catch_reach")
    )

    def run(extra: float) -> float:
        receiver.segments.clear()
        receiver.t, receiver.x, receiver.z = 0.0, start_x, start_z
        receiver.hold(STANCE, SNAP + 0.1)
        if extra > 0.05:
            length = math.hypot(before[0] - start_x, before[1] - start_z) + extra
            side = 1 if catch_z < play.z else -1  # the break turns back toward the middle
            receiver.run(*_waypoint((start_x, start_z), before, length, side), facing)
        receiver.run(*before, facing)
        share = 0.15 / 0.27  # the reach is split by the two catch frames' time
        mid = (before[0] + (catch_x - before[0]) * share, before[1] + (catch_z - before[1]) * share)
        receiver.move(poses[0], 0.15, *mid, facing).move(poses[1], 0.12, catch_x, catch_z, facing)
        return receiver.t

    extra = 0.0  # yards the route runs longer than straight, added up
    catch_t = run(extra)
    if catch_t < not_before:  # a defender needs longer to get there: a longer route
        extra += (not_before - catch_t) * receiver.speed
        catch_t = run(extra)
    flight = _flight(play, catch_x, catch_z, qb_x, air)
    release = catch_t - flight
    if release < earliest:
        thrown = math.hypot(catch_x - qb_x, catch_z - play.z)
        if not deep:
            need = catch_t - earliest
            if need > 0.3 and thrown / (need - 0.25) <= BULLET:
                return catch_t, earliest, need
            flight = 0.25 + thrown / BULLET
        extra += (earliest + flight - catch_t) * receiver.speed
        catch_t = run(extra)
        release = catch_t - flight
    return catch_t, release, flight


def _incomplete(play: _Play, release: float, catch_t: float, x: float, z: float) -> _Play:
    """The ball reaches the target as he does and falls past him, or the defender who covered
    him from the snap gets there with it and gets a hand on it."""
    receiver = play.find("receiver")
    receiver.hold("stand", 0.3)
    landing = (x + play.rng.uniform(1.0, 3.0), 0.12, z + play.rng.uniform(-1.5, 1.5))
    if any(k == "defender" for k, *_ in play.actors):
        defender = play.find("defender")
        if _foul(play, "dpi") is not None and _interfere(
            play, defender, receiver, release, catch_t
        ):
            return _land(play, release, catch_t, x, z)
        mx, mz = _cover(play, defender, receiver, (x, z), 1.0, catch_t - 0.2)
        reach = _side_point(x, z, mx, mz, 0.5)
        defender.move("lunge", 0.2, *reach, "left" if mx > x else "right").hold("stand", 0.3)
    play.fly(release, catch_t + 0.12, BallEnd(actor="passer", hold="hand"), BallEnd(point=landing))
    play.rest(catch_t + 0.12, 1e9, landing)
    return play


def _called_on(play: _Play, track: _Track) -> bool:
    """Whether this player is the one the coverage foul was called on: by ESPN's penalized
    player, or by the text's name for him. A foul is never drawn on someone else."""
    foul = next(
        (_foul(play, kind) for kind in ("opi", "holding", "contact") if _foul(play, kind)), None
    )
    if foul is None:
        return False
    key, espn_id, role, *_ = play.entry(track)
    if foul.team == play.facts.offense:  # offensive pass interference: the receiver pushed off
        return role in ("tackler", "assistedBy", "passDefender", "penalized")
    if espn_id and espn_id in play.ids("penalized"):
        return True
    return (
        bool(foul.player) and (play.names.get(espn_id or "") or play.labels.get(key)) == foul.player
    )


def _coverage_foul(
    play: _Play, cover: _Track, receiver: _Track, release: float, catch_t: float
) -> None:
    """A foul in coverage on a completed pass, drawn where it happens (OWN-037): holding is a grab
    before the throw; illegal contact a shove more than 5 yards past the line before the throw;
    offensive pass interference the receiver pushing off the defender while the ball is in the
    air. The receiver keeps his pace, so the ball still meets him."""
    rng = play.rng
    if _foul(play, "opi") is not None:
        name, hit_t = "opi", release + (catch_t - release) * rng.uniform(0.35, 0.7)
    elif _foul(play, "contact") is not None:
        name, hit_t = "contact", 0.0
        for t in (SNAP + 0.6 + 0.1 * k for k in range(30)):
            if t < release - 0.2 and _at(receiver, t)[0] > play.los + 5.5:
                hit_t = t
                break
    elif _foul(play, "holding") is not None:
        name, hit_t = "holding", max(SNAP + 0.9, min(release - 0.3, SNAP + rng.uniform(1.0, 1.6)))
    else:
        return
    if hit_t <= SNAP + 0.3:
        return
    rx, rz = _at(receiver, hit_t)
    _cover(play, cover, receiver, (rx, rz), 0.8, hit_t)
    ax, az = _at(receiver, hit_t + 0.25)
    if name == "opi":  # he extends his arms into the defender, who staggers back
        cover.move("stumble", 0.3, cover.x + 1.0, cover.z, "left")
    elif name == "holding":  # a grab as he goes by: no faster than a wrap moves
        reach = min(1.4, math.hypot(ax - cover.x, az + 0.6 - cover.z))
        heading = math.atan2(az + 0.6 - cover.z, ax - cover.x)
        cover.move(
            "wrap",
            0.25,
            cover.x + reach * math.cos(heading),
            cover.z + reach * math.sin(heading),
            "right",
        )
    else:
        cover.move("drive", 0.2, cover.x + (ax - cover.x) * 0.4, cover.z + (az - cover.z) * 0.4)
    play.contact[name] = (hit_t, rx, rz)


def _land(play: _Play, release: float, catch_t: float, x: float, z: float) -> _Play:
    """The pass comes down where he would have caught it: catchable, and incomplete."""
    landing = (x + play.rng.uniform(0.5, 1.5), 0.12, z + play.rng.uniform(-0.8, 0.8))
    play.fly(release, catch_t + 0.12, BallEnd(actor="passer", hold="hand"), BallEnd(point=landing))
    play.rest(catch_t + 0.12, 1e9, landing)
    return play


def _interfere(
    play: _Play, defender: _Track, receiver: _Track, release: float, catch_t: float
) -> bool:
    """Defensive pass interference, as the owner set it out (OWN-037): after the release and
    before the ball arrives, more than a yard past the line, the cover man plays through the
    receiver's back, arm-bars him, or cuts off his path instead of playing the ball. The receiver
    stumbles and can't get to a ball that was catchable; the flag comes at the contact."""
    rng = play.rng
    for share in (rng.uniform(0.35, 0.75), 0.5, 0.8):
        hit_t = release + (catch_t - release) * share
        rx, rz = _at(receiver, hit_t)
        if rx > play.los + 1.0:
            break
    else:
        return False
    action = rng.choice(("back", "arm", "cut"))
    gap = {"back": 1.0, "arm": 0.8, "cut": 1.0}[action]
    behind = (
        (rx - 1.5, rz)
        if action == "back"
        else (rx + 1.5, rz)
        if action == "cut"
        else (rx, rz + 1.2)
    )
    mx, mz = _cover(play, defender, receiver, behind, gap, hit_t - 0.1)
    _cut(receiver, hit_t)
    pose = {"back": "lunge", "arm": "wrap", "cut": "drive"}[action]
    defender.move(pose, 0.25, rx, rz + (0.5 if action == "arm" else 0.0)).hold("stand", 0.3)
    receiver.move("stumble", 0.3, rx + 1.0, rz).move("stumble", 0.2, rx + 1.4, rz)
    receiver.hold("stand", 0.4)
    play.contact["dpi"] = (hit_t, rx, rz)
    return True


def _named(play: _Play, pattern: str, side: str) -> tuple[str | None, str] | None:
    """A player the text names who ESPN lists only as "other", such as the intended receiver:
    his ESPN ID when the roster name matches, or the only "other" with a position on that side
    of the ball, or None for the ID when neither tells. None when the text names nobody."""
    found = re.search(pattern, play.facts.text)
    if not found:
        return None
    name = found.group(1)
    others = [espn_id for espn_id in play.ids("other") if play.position(espn_id, side)]
    by_name = [espn_id for espn_id in play.ids("other") if play.names.get(espn_id) == name]
    if by_name:
        return by_name[0], name
    if len(others) == 1 and not any(play.names.get(o) for o in others):
        return others[0], name
    return None, name


def _interception(play: _Play) -> _Play | None:
    """The intended receiver runs his route and the defender covering him undercuts it, catching
    the ball a step in front of him as it arrives (OWN-037). A pass tipped at the line, by the
    player ESPN names in parentheses after the interceptor, pops up to the interceptor."""
    facts = play.facts
    passing = facts.passing
    assert passing is not None and passing.catch_spot is not None
    pickers = play.ids("returner") or play.ids("passDefender")
    if not pickers:
        return None
    pick_x, pick_z = float(passing.catch_spot), play.lane(passing.side)
    air = pick_x - play.los
    steps = _steps_for(max(air, 1.0))
    qb = _snap(
        play,
        "passer",
        play.ids("passer")[0],
        "passer",
        play.los - (5.0 if facts.shotgun else UNDER),
        facts.shotgun,
    )
    _drop(play, qb, steps)
    earliest = qb.t + 0.55
    intended = _named(play, rf"intended for ({_NAME})", "offense")
    tip = _named(play, rf"INTERCEPTED by {_NAME} \(({_NAME})\)", "defense")
    tipped = tip is not None and air < 4.0
    picker = play.add(
        "interceptor",
        pickers[0],
        "interceptor",
        "defense",
        play.track(pick_x + 5.0, pick_z + 3.0, "defense"),
        "left",
    )
    _place(play, picker, pick_x + 0.6, pick_z, earliest + 1.0, SNAP + 0.3)
    needed = (
        SNAP
        + 0.2
        + max(0.0, math.hypot(picker.x - pick_x, picker.z - pick_z) - 0.6) / picker.speed
        + 0.4
    )
    receiver = None
    if intended is not None:
        side = 1 if pick_z >= play.z else -1
        target = (max(pick_x, play.los + 2.0) + 1.0, pick_z + 0.8 * side)
        lateral = play.rng.uniform(2.0, 6.0)
        start_z = min(51.5, max(1.5, target[1] + side * lateral))
        start = _apart(play, None, play.los - 0.5, start_z)
        receiver = play.add(
            "receiver",
            intended[0],
            "receiver",
            "offense",
            play.track(*start, "receiver"),
            "right",
            None if intended[0] else intended[1],
        )
        arrive, release, _ = _route(
            play, receiver, target, air >= 18, air, qb.x, earliest, 0.0 if tipped else needed
        )
        receiver.hold("stand", 0.3)
    else:
        release = max(
            earliest,
            SNAP + play.rng.uniform(1.9, 2.6),
            needed - _flight(play, pick_x, pick_z, qb.x, air),
        )
    _throw(qb, release)
    play.release("passer", release)
    origin = BallEnd(actor="passer", hold="hand")
    if tipped and tip is not None:
        # At the line the pass meets a rusher's raised hands and pops up.
        tip_t = release + 0.18
        point = (play.los + 0.8, 2.6, play.z + play.rng.uniform(-1.5, 1.5))
        tipper = play.add(
            "tipper",
            tip[0],
            "passDefender",
            "defense",
            play.track(play.los + 1.0, point[2] + 0.4, "defense"),
            "left",
            None if tip[0] else tip[1],
        )
        tipper.hold(STANCE, SNAP + 0.2)
        tipper.run(point[0] + 0.2, point[2] + 0.4)
        settle(tipper, tip_t - 0.3)
        tipper.hold("arms_jump", 0.3).hold("arms_up", 0.3).hold("stand", 0.3)
        play.fly(release, tip_t, origin, BallEnd(point=point))
        origin = BallEnd(point=point)
        catch_t = tip_t + 0.7 + 0.04 * math.hypot(pick_x - point[0], pick_z - point[2])
        play.fly(tip_t, catch_t, origin, BallEnd(actor="interceptor", hold="hands"), "tumble")
    else:
        catch_t = release + _flight(play, pick_x, pick_z, qb.x, air)
        if receiver is not None:
            catch_t = min(catch_t, arrive - 0.02)
        play.fly(release, catch_t, origin, BallEnd(actor="interceptor", hold="hands"))
    if receiver is not None and not tipped:
        _cover(play, picker, receiver, (pick_x, pick_z), 0.6, catch_t - 0.37)
    else:
        _close(play, picker, pick_x + 0.6, pick_z, catch_t - 0.37, react=SNAP + 0.3, placed=True)
    picker.hold("catch_high_e", 0.25).hold("catch_high", 0.12)
    play.hold_ball("interceptor", catch_t)
    picker.move("catch_secure", 0.2, pick_x - 0.6, pick_z)
    _carry(play, picker, "interceptor", pick_z, way=-1)
    return play


# Sacks and runs -------------------------------------------------------------------------------


def _sack(play: _Play) -> _Play:
    facts = play.facts
    qb = _snap(
        play,
        "passer",
        play.ids("passer")[0],
        "passer",
        play.los - (5.0 if facts.shotgun else UNDER),
        facts.shotgun,
    )
    spot = play.end
    drop_to = spot + 0.6  # where the hit lands: ESPN's spot is where he went down
    qb.move("DROP", max(0.3, abs(qb.x - drop_to) / play.rng.uniform(3.2, 3.8)), drop_to, play.z)
    # He works the pocket, then escapes to his right, the far side, and is caught there
    # (OWN-037); near that sideline he escapes left instead.
    escape = play.rng.uniform(0.55, 0.9)
    way_z = 1 if play.z + qb.speed * escape < FIELD_WIDTH - 3.0 else -1
    run_z = play.z + way_z * qb.speed * escape
    contact = max(qb.t + 0.5 + escape, SNAP + play.rng.uniform(2.2, 3.0))
    rushers = play.ids("sackedBy")[:2]
    plans: list[tuple[str, _Track, int]] = []
    for index, espn_id in enumerate(rushers):
        side = 1 if index == 0 else -1
        start = (play.los + 1.0, play.z + side * play.rng.uniform(3.0, 7.0))
        code = play.position(espn_id, "defense")
        aligned = A.spot(code, play.context(), chance=0.75 if side > 0 else 0.25) if code else None
        if aligned is not None:  # rushes from where his position lines up (OWN-036)
            start = _snap_spot(play, "defense", *aligned)
            if plans and math.hypot(start[0] - plans[0][1].x, start[1] - plans[0][1].z) < 1.2:
                start = (start[0], start[1] + 1.5 * side)
        track = play.track(*start, "defense")
        plans.append((espn_id, track, side))
        # A rusher who would arrive late makes the quarterback hold on a little longer.
        near = _side_point(spot + 0.3, run_z + 0.3 * side, start[0], start[1], 2.4)
        straight = math.hypot(near[0] - start[0], near[1] - start[1])
        contact = max(contact, SNAP + 0.15 + straight / track.speed + 0.45)
    settle(qb, contact - 0.13 - abs(run_z - qb.z) / qb.speed, "pocket", climb=False)
    qb.run(drop_to, run_z, "right")
    qb.move("hit_back", 0.1, spot + 0.3, run_z).move("fall_back_30", 0.12, spot + 0.1, run_z)
    qb.move("fall_back_60", 0.15, spot, run_z).hold("ground_back", 0.3)
    for index, (espn_id, track, side) in enumerate(plans):
        rusher = play.add(f"sacker_{index + 1}", espn_id, "sackedBy", "defense", track, "left")
        rusher.hold(STANCE, SNAP + 0.15)
        near = _side_point(spot + 0.3, run_z + 0.3 * side, track.x, track.z, 2.4)
        # Around the edge: a longer path at his own pace, not a slow straight one.
        rusher.run_by(*near, contact + 0.06 * index - 0.45, side)
        _wrap_toward(rusher, spot + 0.3, run_z + 0.3 * side)
    return play


def _spike(play: _Play) -> _Play:
    """Under center, the snap and straight into the turf to stop the clock."""
    passer = (play.ids("passer") or play.ids("rusher"))[0]
    track = _snap(play, "passer", passer, "passer", play.los - UNDER, False)
    track.hold("spike", 0.3).hold("stand", 0.3)
    thrown = track.t - 0.3
    play.release("passer", thrown)
    landing = (track.x + 0.8, 0.12, track.z)
    play.fly(thrown, thrown + 0.18, BallEnd(actor="passer", hold="hand"), BallEnd(point=landing))
    play.rest(thrown + 0.18, 1e9, landing)
    return play


def _kneel(play: _Play) -> _Play:
    rusher = (play.ids("rusher") or play.ids("passer"))[0]
    track = play.add(
        "rusher",
        rusher,
        "rusher",
        "offense",
        play.track(play.los - UNDER, play.z, "quarterback"),
        "right",
    )
    _center(play)
    track.hold("ready", SNAP)
    play.rest(0.0, SNAP, (play.los, 0.15, play.z))
    play.hold_ball("rusher", SNAP)
    shift = play.end - track.x
    kneel_reach = 0.45 * STILL
    if abs(shift) > kneel_reach:
        step = shift - math.copysign(kneel_reach, shift)
        track.move("DROP", max(0.2, abs(step) / 3.5), track.x + step, track.z)
    track.move("kneel", 0.5, play.end, play.z).hold("kneel", 0.3)
    return play


_GAPS = {"guard": 1.8, "tackle": 3.6, "end": 7.0, "middle": 0.0}


def _run(play: _Play) -> _Play:
    facts = play.facts
    run = facts.run
    style = run.style if run else "run"
    rusher = (play.ids("rusher") or play.ids("passer"))[0]
    sign = (
        -1
        if run and run.side == "left"
        else 1
        if run and run.side == "right"
        else play.rng.choice((-1, 1))
    )
    hole_z = play.z + sign * _GAPS.get(run.gap if run and run.gap else "guard", 1.8)
    if style == "scramble":
        qb = _snap(
            play,
            "rusher",
            rusher,
            "rusher",
            play.los - (5.0 if facts.shotgun else UNDER),
            facts.shotgun,
        )
        _drop(play, qb, 3)
        # His look in the pocket, which a play built to time lengthens or shortens (OWN-052).
        look = play.rng.uniform(0.7, 1.3) - SCRAMBLE_LOOK + play.extra.get("mesh", SCRAMBLE_LOOK)
        settle(qb, qb.t + look, "pocket")
        out = min(FIELD_WIDTH - 3.0, max(3.0, play.z + sign * play.rng.uniform(4.0, 9.0)))
        qb.run(max(qb.x, play.los - 3.0), out)
        _carry(play, qb, "rusher", out, way=1)
        return play
    if style == "sneak":
        qb = _snap(play, "rusher", rusher, "rusher", play.los - UNDER, False)
        # A push in the pile: the drive pose, at a pile's pace.
        push = max(0.4, (play.end - qb.x) / 3.0) + play.extra.get("drive", 0.0)
        qb.move("drive", push, play.end, play.z).hold("ground", 0.3)
        return play
    back = 5.0 if facts.shotgun else 7.0
    start_z = play.z + (play.rng.choice((-1.5, 1.5)) if facts.shotgun else 0.0)
    kind = A.group(play.position(rusher, "offense"))
    if kind == "QB":  # a designed quarterback run: he takes the snap where he lines up
        back, start_z = (5.0 if facts.shotgun else UNDER), play.z
    elif kind in ("WR", "TE"):  # a sweep or end-around: from the slot on the side of the run
        back, start_z = 1.0, min(FIELD_WIDTH - 2.0, max(2.0, play.z + 6.5 * sign))
    elif kind == "FB":
        back = 4.5
    track = play.add(
        "rusher",
        rusher,
        "rusher",
        "offense",
        play.track(play.los - back, start_z, "rusher"),
        "right",
    )
    quarterback = play.unit("quarterback") if kind != "QB" else None
    drawn = {espn_id for _, espn_id, *_ in play.actors}
    if quarterback is not None and quarterback[0] not in drawn and quarterback[0] != rusher:
        _handoff(play, track, quarterback, start_z, jet=kind in ("WR", "TE"))
    else:
        _center(play)
        delay = min(play.extra.get("mesh", 0.0), HANDOFF_BY - 0.02 - (SNAP + 0.55))
        track.hold(STANCE, SNAP + 0.1 + delay)
        play.rest(0.0, SNAP, (play.los, 0.15, play.z))
        handoff = SNAP + 0.55 + delay
        play.fly(
            SNAP,
            handoff,
            BallEnd(point=(play.los, 0.3, play.z)),
            BallEnd(actor="rusher", hold="chest"),
        )
        play.hold_ball("rusher", handoff)
    if play.end > play.los + 1:
        hole = (play.los + 0.3, hole_z)
        bend = play.extra.get("path", 0.0)
        straight = math.hypot(hole[0] - track.x, hole[1] - track.z)
        if bend > 0 and straight > 0.5:
            # A wider path to the hole at his own pace: he presses outside, then cuts up.
            length = min(straight + bend * track.speed, straight * 3.0)
            side = 1 if hole_z >= track.z else -1
            track.run(*_waypoint((track.x, track.z), hole, length, side))
        track.run(*hole)
    _carry(play, track, "rusher", hole_z, way=1)
    return play


def _handoff(
    play: _Play, back: _Track, quarterback: tuple[str, str], back_z: float, jet: bool = False
) -> None:
    """The quarterback takes the snap and hands off at once (OWN-037): the back runs through the
    mesh beside him and takes the ball as he passes; the quarterback carries out his fake. If the
    quarterback needs a moment longer to get to the mesh, the back times his start to it. A
    receiver or tight end on a sweep comes across in jet motion, moving along the line before
    the snap as the rules allow, and takes it right behind the quarterback."""
    shotgun = bool(play.facts.shotgun)
    qb = _snap(
        play,
        "quarterback",
        quarterback[0],
        "quarterback",
        play.los - (5.0 if shotgun else UNDER),
        shotgun,
        play.names.get(quarterback[0]) or quarterback[1],
    )
    side = 1 if back_z >= play.z else -1
    mesh = (qb.x + 0.6, play.z + 0.8 * side) if shotgun else (play.los - 3.4, play.z + 0.6 * side)
    if jet:
        mesh = (qb.x + (1.4 if shotgun else -0.9), play.z)
    across = math.hypot(mesh[0] - back.x, mesh[1] - back.z) or 1.0
    ux, uz = (mesh[0] - back.x) / across, (mesh[1] - back.z) / across
    into = (mesh[0] - ux * 0.9, mesh[1] - uz * 0.9)
    spot = (mesh[0] - 0.2, mesh[1] - 0.75 * side)  # the quarterback beside the mesh
    ready = qb.t + math.hypot(spot[0] - qb.x, spot[1] - qb.z) / qb.speed + 0.2
    travel = math.hypot(into[0] - back.x, into[1] - back.z) / back.speed
    if jet:  # in motion before the snap, timed to reach the mesh just after it
        back.hold(STANCE, max(0.2, max(ready, SNAP + 0.45) - 0.12 - travel))
    else:
        reach = SNAP + 0.1 + travel + 0.12
        wait = max(0.0, ready - reach)
        # A slower mesh, but the handoff stays right after the snap (OWN-037).
        delay = min(play.extra.get("mesh", 0.0), max(0.0, HANDOFF_BY - 0.02 - (reach + wait)))
        back.hold(STANCE, SNAP + 0.1 + wait + delay)
    back.run(*into)
    handoff = back.t + 0.12
    back.move("take", 0.25, mesh[0] + ux * 0.9, mesh[1] + uz * 0.9)
    leave = handoff - 0.2 - math.hypot(spot[0] - qb.x, spot[1] - qb.z) / qb.speed
    if leave > qb.t + 1e-3:
        settle(qb, leave, "pocket")
    if math.hypot(spot[0] - qb.x, spot[1] - qb.z) > 0.05:
        qb.move("DROP", max(0.15, math.hypot(spot[0] - qb.x, spot[1] - qb.z) / qb.speed), *spot)
    qb.move("handoff_give", max(0.05, handoff - qb.t), *spot)
    qb.move("handoff_follow", 0.45, spot[0] - 0.4, spot[1] - 0.6 * side).hold("stand", 0.3)
    play.release("quarterback", handoff)
    play.fly(
        handoff,
        handoff + 0.08,
        BallEnd(actor="quarterback", hold="hand"),
        BallEnd(actor="rusher", hold="chest"),
    )
    play.hold_ball("rusher", handoff + 0.08)


# Shared pieces --------------------------------------------------------------------------------


def _snap_spot(play: _Play, side: str, x: float, z: float) -> tuple[float, float]:
    """Where a player can stand at the snap (OWN-035): the offense on or behind the line of
    scrimmage, the defense on or beyond it, no deeper than a safety."""
    if side == "offense":
        x = min(play.los - 0.5, max(play.los - 8.0, x))
    else:
        x = max(play.los + 1.0, min(play.los + DEEPEST, x))
    return x, min(FIELD_WIDTH - 1.0, max(1.0, z))


def _place(play: _Play, track: _Track, x: float, z: float, arrive: float, react: float) -> None:
    """Start a new player where his position lines up (OWN-036), with the play deciding a
    defensive back's side and putting a corner or nickel back over the receiver the pass went
    to. Without a known
    position: within the sprint he has time for after the snap, since nobody moves before it.
    Either way he stands where he could at the snap, clear of anyone already there."""
    _, espn_id, _, side, _, _ = play.entry(track)
    code = play.position(espn_id, side)
    aligned = A.spot(code, play.context(), toward=z, chance=play.rng.random()) if code else None
    if aligned is not None:
        ax, az = aligned
        receiver = next((t for k, *_, t, _ in play.actors if k == "receiver"), None)
        if A.group(code) in ("CB", "NB") and receiver is not None:
            # A defensive back named on a pass covered its target: he lines up over him.
            az = receiver.segments[0].z0 if receiver.segments else receiver.z
        track.x, track.z = _apart(play, track, *_snap_spot(play, side, ax, az))
        return
    sprint = min(play.rng.uniform(1.0, 1.8), max(0.3, arrive - max(react, track.t, SNAP + 0.2)))
    reach = min(track.speed * sprint, math.hypot(track.x - x, track.z - z) or track.speed * sprint)
    angle = math.atan2(track.z - z, track.x - x)
    track.x, track.z = _apart(
        play,
        track,
        *_snap_spot(play, side, x + reach * math.cos(angle), z + reach * math.sin(angle)),
    )


def _apart(play: _Play, track: _Track | None, x: float, z: float) -> tuple[float, float]:
    """Move a start across the field until nobody else stands within a yard of it."""
    others = [
        (t.segments[0].x0, t.segments[0].z0) if t.segments else (t.x, t.z)
        for *_, t, _ in play.actors
        if t is not track
    ]
    for step in (0.0, 1.3, -1.3, 2.6, -2.6, 3.9, -3.9):
        candidate = min(FIELD_WIDTH - 1.0, max(1.0, z + step))
        if all(math.hypot(x - ox, candidate - oz) >= 1.0 for ox, oz in others):
            return x, candidate
    return x, z


def _soonest(track: _Track, x: float, z: float) -> float:
    """When a new player who starts moving at the snap can be at (x, z)."""
    return SNAP + 0.2 + math.hypot(track.x - x, track.z - z) / track.speed


def _waiting_at_catch(play: _Play, x: float, z: float, time: float) -> bool:
    return play.catch is not None and (
        time < play.catch[2] - 0.3 and math.hypot(x - play.catch[0], z - play.catch[1]) < 1.3
    )


def _close(
    play: _Play,
    track: _Track,
    x: float,
    z: float,
    arrive: float,
    react: float,
    facing: str | None = None,
    placed: bool = False,
) -> None:
    """Get a player to (x, z) at `arrive`, at his own pace. A new one starts where he could stand
    at the snap and sets there with a side step, holding his ground, until he breaks; he can't
    leave before the snap. One already on the field runs from where he is."""
    if not track.segments:
        if not placed:
            _place(play, track, x, z, arrive, react)
        start = SNAP + 0.2
        _, espn_id, _, side, _, _ = play.entry(track)
        code = play.position(espn_id, side)
        first = (
            A.read(code, play.context(), (track.x, track.z), side == "defense") if code else None
        )
        if first is not None:
            # His position's first move for this kind of play, when there's time for it and
            # still to get to the ball (OWN-036).
            pose, seconds, rx, rz, face = first
            rz = min(FIELD_WIDTH - 1.0, max(1.0, rz))
            if pose == "RUN":
                seconds = math.hypot(rx - track.x, rz - track.z) / track.speed
            after = math.hypot(x - rx, z - rz) / track.speed
            if (
                seconds > 0.05
                and start + seconds + after <= arrive
                and not _waiting_at_catch(play, rx, rz, start + seconds)
            ):
                settle(track, start, facing=facing)
                track.move(pose, seconds, rx, rz, face)
                settle(track, arrive - after, facing=facing)
                track.run(x, z, facing)
                return
        leave = max(arrive - math.hypot(track.x - x, track.z - z) / track.speed, start)
        settle(track, leave, facing=facing)
        track.run(x, z, facing)
        return
    track.run_by(x, z, arrive, play.rng.choice((-1, 1)), facing)


def _foul(play: _Play, kind: str) -> PenaltyFacts | None:
    """The play's foul of this kind: "dpi", "opi", "holding" or "contact"."""
    words = {
        "dpi": ("defensive pass interference",),
        "opi": ("offensive pass interference",),
        "holding": ("defensive holding",),
        "contact": ("illegal contact",),
    }[kind]
    return next((p for p in play.fouls if any(w in (p.type or "").lower() for w in words)), None)


def _cut(track: _Track, t: float) -> None:
    """Drop everything in a timeline after time t, ending it where he is then."""
    x, z = _at(track, t)
    kept = []
    for seg in track.segments:
        if seg.end <= t + 1e-9:
            kept.append(seg)
        elif seg.start < t:
            kept.append(
                seg.model_copy(update={"end": round(t, 4), "x1": round(x, 3), "z1": round(z, 3)})
            )
    track.segments[:] = kept
    track.t, track.x, track.z = t, x, z


def _at(track: _Track, t: float) -> tuple[float, float]:
    """Where a player is at time t, from his timeline so far."""
    for seg in track.segments:
        if seg.start <= t < seg.end:
            share = (t - seg.start) / (seg.end - seg.start) if seg.end > seg.start else 1.0
            return seg.x0 + (seg.x1 - seg.x0) * share, seg.z0 + (seg.z1 - seg.z0) * share
    if track.segments and t < track.segments[0].start:
        return track.segments[0].x0, track.segments[0].z0
    return track.x, track.z


def _side_point(
    x: float, z: float, from_x: float, from_z: float, gap: float
) -> tuple[float, float]:
    """The point `gap` yards from (x, z) toward where a player comes from, so a tackler meets the
    carrier from his own side and never runs past him to come back (OWN-037)."""
    dx, dz = from_x - x, from_z - z
    distance = math.hypot(dx, dz)
    if distance < 1e-6:
        return x, z
    share = min(gap, distance) / distance
    return x + dx * share, z + dz * share


def _wrap_toward(
    track: _Track,
    x: float,
    z: float,
    facing: str | None = None,
    pile: tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> None:
    """The tackler's finish from whichever side he comes: lunge, wrap, drive and fall into the
    carrier at (x, z), then get up. With a `pile` of (yards along, yards across, seconds) he stays
    wrapped on the carrier while the pile moves, then goes down with him."""
    dx, dz = track.x - x, track.z - z
    distance = math.hypot(dx, dz) or 1.0
    ux, uz = dx / distance, dz / distance
    facing = facing or ("left" if dx > 0 else "right")
    track.move("lunge", max(0.2, (distance - 1.1) / 7.0), x + ux * 1.1, z + uz * 1.1, facing)
    track.move("wrap", 0.15, x + ux * 0.5, z + uz * 0.5, facing)
    along, across, seconds = pile
    if seconds > 0:
        x, z = x + along, z + across
        _churn(track, ("drive", "wrap"), seconds, x + ux * 0.5, z + uz * 0.5, facing)
    for pose, step, gap in (("drive", 0.1, 0.3), ("fall_60", 0.2, 0.2)):
        track.move(pose, step, x + ux * gap, z + uz * gap, facing)
    track.hold("ground", 1.4, facing).hold("rise_1", 0.3, facing).hold("rise_2", 0.3, facing)
    track.hold("rise_3", 0.3, facing).hold(IDLE, 0.3, facing)


def _churn(
    track: _Track,
    poses: tuple[str, str],
    seconds: float,
    x: float,
    z: float,
    facing: str | None = None,
) -> None:
    """Move to (x, z) over `seconds` in steps of about 0.2 s, alternating two contact poses, so a
    pile moves with legs churning rather than as a still frame."""
    steps = max(1, round(seconds / 0.2))
    x0, z0 = track.x, track.z
    for i in range(1, steps + 1):
        share = i / steps
        track.move(
            poses[(i - 1) % 2],
            seconds / steps,
            x0 + (x - x0) * share,
            z0 + (z - z0) * share,
            facing,
        )


def _cover(
    play: _Play,
    track: _Track,
    receiver: _Track,
    around: tuple[float, float],
    gap: float,
    meet_t: float,
    facing: str = "left",
    stay: bool = False,
) -> tuple[float, float]:
    """A defender covering the receiver (OWN-037): set in his stance until the snap, then a
    backpedal that mirrors the receiver across the field, keeping a cushion that closes as the
    play goes, turning to run when the receiver outruns a backpedal. He breaks as late as still
    gets him `gap` yards from `around`, on the side he comes from, at `meet_t`, and never sooner.
    With `stay` he keeps covering through `meet_t` without breaking, as on a completed pass he'll
    tackle after the catch. Returns where he is then."""
    start = SNAP + 0.2
    if not track.segments:
        track.hold(STANCE, start, facing)
    rx, _ = _at(receiver, track.t)
    cushion0 = max(1.5, track.x - rx)
    # His drop at the snap, into his zone or off his man, before he reads the receiver.
    _, espn_id, _, side, _, _ = play.entry(track)
    drop = {"LB": 3.5, "CB": 3.0, "NB": 3.0, "S": 2.0}.get(
        A.group(play.position(espn_id, side)) or "", 3.0
    )
    home = track.x
    steps: list[tuple[float, float, float, float, float, float, str, str]] = []
    t, x, z = track.t, track.x, track.z
    while t < meet_t - 1e-3:
        dt = min(0.25, meet_t - t)
        rx, rz = _at(receiver, t + dt)
        closing = min(1.0, (t + dt - start) / max(0.5, meet_t - start))
        want_x, want_z = rx + max(2.0, cushion0 * (1.0 - closing)), rz  # never on top of him
        want_x = max(want_x, home + drop * min(1.0, (t + dt - start) / 0.8))
        back = want_x - x
        if back > BACKPEDAL * dt + 0.2:  # outrun: he turns and runs to stay over the top
            stride = math.hypot(back, want_z - z) or 1.0
            reach = min(stride, track.speed * dt)
            nx, nz = x + back / stride * reach, z + (want_z - z) / stride * reach
            pose, face = "RUN", "right"
        else:
            nx = x + max(0.0, min(back, BACKPEDAL * dt))
            nz = z + max(-3.0 * dt, min(3.0 * dt, want_z - z))
            moving = math.hypot(nx - x, nz - z) / dt
            pose, face = ("BACKPEDAL", facing) if moving > 1.0 else (STANCE, facing)
            if pose == STANCE:
                nx, nz = x, z + max(-STILL * dt * 0.9, min(STILL * dt * 0.9, want_z - z))
        if pose == STANCE and math.hypot(x - around[0], z - around[1]) < 1.3:
            # Keep moving through this part of the coverage; the defender should
            # not settle at the future catch spot while the receiver is still on his route.
            nx = min(around[0] + 1.5, x + BACKPEDAL * dt)
            pose = "BACKPEDAL"
        steps.append((t, t + dt, x, z, nx, nz, pose, face))
        t, x, z = t + dt, nx, nz
    keep = len(steps) if stay else 0
    for index in range(len(steps), -1, -1) if not stay else []:
        at_t, at_x, at_z = (
            (steps[index][0], steps[index][2], steps[index][3]) if index < len(steps) else (t, x, z)
        )
        meet = _side_point(*around, at_x, at_z, gap)
        if at_t + math.hypot(meet[0] - at_x, meet[1] - at_z) / track.speed <= meet_t + 1e-6:
            keep = index
            break
    for t0, t1, _x0, _z0, x1, z1, pose, face in steps[:keep]:
        track.move(pose, t1 - t0, x1, z1, face)
    if stay:
        return track.x, track.z
    meet = _side_point(*around, track.x, track.z, gap)
    leave = meet_t - math.hypot(meet[0] - track.x, meet[1] - track.z) / track.speed
    heading = "right" if meet[0] > track.x + 0.3 else facing
    if leave > track.t + 1e-3 and _waiting_at_catch(play, track.x, track.z, track.t):
        track.run_by(*meet, meet_t, play.rng.choice((-1, 1)), heading, wait_first=False)
    else:
        if leave > track.t + 1e-3:
            settle(track, leave, facing=facing)
        track.run(*meet, heading)
    return meet


def _trail(
    play: _Play,
    key: str,
    carrier: _Track,
    end: tuple[float, float],
    shove: bool,
    at: float | None = None,
) -> None:
    """A tackler already on the field, such as a cover man, on a play that ends without a tackle:
    he runs the carrier out of bounds and shoves him at the sideline, or trails him into the end
    zone, then stops (OWN-037)."""
    tacklers = list(dict.fromkeys(play.ids("tackler") + play.ids("assistedBy")))[:3]
    drawn = {espn_id: (t, k) for k, espn_id, *_, t, _ in play.actors}
    for index, espn_id in enumerate(tacklers):
        if espn_id not in drawn or drawn[espn_id][1] == key:
            continue
        chaser = drawn[espn_id][0]
        inside = 1.5 if end[1] < FIELD_WIDTH / 2 else -1.5
        target = (end[0] - 0.6 * index, min(FIELD_WIDTH - 1.0, max(1.0, end[1] + inside)))
        arrive = max(
            (at if at is not None else carrier.t) - 0.2,
            chaser.t + math.hypot(target[0] - chaser.x, target[1] - chaser.z) / chaser.speed,
        )
        heading = "right" if target[0] > chaser.x else "left"
        chaser.run_by(*target, arrive, play.rng.choice((-1, 1)), heading)
        if shove:
            chaser.move("drive", 0.2, target[0], target[1] - inside * 0.4, heading)
        chaser.hold(IDLE, 0.3, heading)


def _carry(
    play: _Play,
    track: _Track,
    key: str,
    lane_z: float,
    way: int,
    start_line: float | None = None,
    released: float | None = None,
) -> None:
    """Run the ball to ESPN's spot at the carrier's own pace and end the play there: tackled, out
    of bounds or in the end zone. If a tackler can't get there in time, the carrier weaves. On a
    kick return the coverage starts at `start_line` and may not move before `released`."""
    facts = play.facts
    rng = play.rng
    spot = play.end
    if facts.touchdown:
        goal = 100.0 if way > 0 else 0.0
        track.run(
            goal + way * rng.uniform(1.5, 3.5), min(48.0, max(5.0, lane_z + rng.uniform(-3.0, 3.0)))
        )
        for pose, seconds in (
            ("spike", 0.35),
            ("arms_up", 0.35),
            ("arms_jump", 0.3),
            ("arms_up", 0.3),
        ):
            track.hold(pose, seconds)
        track.hold("point", 0.3)
        _trail(play, key, track, (goal - way * 3.0, track.z), shove=False)
        return
    if facts.out_of_bounds:
        track.run(spot, 0.6 if lane_z < FIELD_WIDTH / 2 else FIELD_WIDTH - 0.6)
        out_at = track.t
        track.hold("stand", 0.3)
        _trail(play, key, track, (spot - way * 0.4, track.z), shove=True, at=out_at)
        return
    z = min(FIELD_WIDTH - 2.0, max(2.0, lane_z + rng.uniform(-3.0, 3.0)))
    before = spot - way * 0.7
    running = way * (before - track.x) > 0.3
    if not running:  # no ground left to gain: absorb it where he is, in his lane
        z = track.z
    # Built to the real time, a run may meet the tacklers sooner and drive the pile to the spot
    # (OWN-052). With no ground left ahead of him, the pile shifts sideways as well: it always
    # moves at least half a yard a second, so it never reads as a still frame.
    drive = play.extra.get("drive", 0.0)
    room = max(0.0, way * (before - track.x) - 0.3) if running else 0.0
    pile = min(drive * DRIVE_PACE, room)
    shift = math.sqrt(max(0.0, (0.5 * drive) ** 2 - pile**2))
    hit = spot - way * pile  # where contact comes
    down_z = min(FIELD_WIDTH - 2.0, max(2.0, z + (shift if z < FIELD_WIDTH / 2 else -shift)))
    before = hit - way * 0.7
    reach = math.hypot(before - track.x, z - track.z)
    contact = (
        track.t + (reach / track.speed if running else max(0.2, abs(track.x - before) / 3.0)) + 0.13
    )
    tacklers = list(dict.fromkeys(play.ids("tackler") + play.ids("assistedBy")))[:3]
    drawn = {espn_id: (t, k) for k, espn_id, *_, t, _ in play.actors}
    for espn_id in tacklers:
        if espn_id in drawn and drawn[espn_id][1] != key:
            # Already on the field, such as a cover man or a passer tackling the interceptor: he
            # chases from where he is, at his pace, and the carrier weaves so he can get there.
            chaser = drawn[espn_id][0]
            near = _side_point(hit, z, chaser.x, chaser.z, 2.4)
            gap = math.hypot(chaser.x - near[0], chaser.z - near[1])
            contact = max(contact, chaser.t + gap / chaser.speed + 0.45)
    weave = rng.choice((-1, 1)) if running else 0
    toward = "right" if way > 0 else "left"
    # Everyone who makes the tackle starts where he could stand at the snap, or for a kick
    # return on his coverage line, and meets the carrier from his own side (OWN-037). If he needs
    # longer to get there, the carrier weaves longer.
    plans: list[tuple[int, float, _Track, bool, int, str | None]] = []
    for index, espn_id in enumerate(tacklers):
        offset = (0.0, 1.6, -1.6)[index]
        role = "tackler" if index == 0 else "assistedBy"
        meet = contact + 0.08 * index
        if espn_id in drawn and drawn[espn_id][1] != key:
            plans.append((index, offset, drawn[espn_id][0], True, rng.choice((-1, 1)), None))
            continue
        behind = key == "interceptor"  # after a pick the offense chases from behind the return
        side_x = -way if behind else way
        tackler = play.add(
            f"tackler_{index + 1}",
            espn_id,
            role,
            "defense" if play.side_of(key) == "offense" else "offense",
            play.track(
                spot + side_x * rng.uniform(7.0, 13.0), z + rng.uniform(-8.0, 8.0), "defense"
            ),
            toward if behind else ("left" if way > 0 else "right"),
        )
        facing = toward if behind else None
        guess = (hit + side_x * 2.4, z + offset - 0.3)
        if start_line is not None:
            # Kick coverage: from its line, never past it, held until the release.
            tackler.x = start_line - abs(rng.uniform(-1.0, 1.0))
            spread = rng.uniform(-14.0, 14.0)
            tackler.z = min(FIELD_WIDTH - 2.0, max(2.0, z + spread))
            code = play.position(espn_id)
            if code and A.group(code):  # gunners wide, everyone else inside (OWN-036)
                middle = FIELD_WIDTH / 2 if facts.template == "kickoff" else play.z
                _, cz = A.coverage_spot(code, play.los, middle, start_line, (spread + 14.0) / 28.0)
                tackler.z = min(FIELD_WIDTH - 2.0, max(2.0, cz))
            tackler.z = _apart(play, tackler, tackler.x, tackler.z)[1]
            choice = rng.choice((-1, 1))
            near = _side_point(hit, z + offset - 0.3, tackler.x, tackler.z, 2.4)
            soonest = (released or 0.0) + math.hypot(
                tackler.x - near[0], tackler.z - near[1]
            ) / tackler.speed
        else:
            _place(play, tackler, *guess, meet - 0.45, meet - 3.0)
            near = _side_point(hit, z + offset - 0.3, tackler.x, tackler.z, 2.4)
            choice, soonest = 0, _soonest(tackler, *near)
        contact = max(contact, soonest + 0.45 - 0.08 * index)
        plans.append((index, offset, tackler, False, choice, facing))
    if running:
        track.run_by(before, z, contact - 0.13, weave, wait_first=False)
    elif abs(track.x - before) > 0.05:
        track.move("stumble", max(0.2, abs(track.x - before) / 3.0), before, z)
        settle(track, contact - 0.13)
    track.move("hit", 0.1, hit - way * 0.4, z)
    if drive > 0:  # legs churning, the pile moving to the spot
        _churn(track, ("drive", "stumble"), drive, spot - way * 0.4, down_z)
    track.move("stumble", 0.1, spot - way * 0.25, down_z)
    track.move("fall_30", 0.1, spot - way * 0.1, down_z).move("fall_60", 0.15, spot, down_z).hold(
        "ground", 0.3
    )
    for index, offset, tackler, chasing, choice, facing in plans:
        meet = contact + 0.08 * index
        target_z = z + offset
        if chasing:
            # From where he is, straight in: set facing the carrier, then break, so a chaser who
            # is already close never bends away and comes again (OWN-037).
            near = _side_point(hit, target_z - 0.3, tackler.x, tackler.z, 2.4)
            heading = "right" if near[0] > tackler.x else "left"
            leave = (
                meet - 0.45 - math.hypot(near[0] - tackler.x, near[1] - tackler.z) / tackler.speed
            )
            if leave > tackler.t + 1e-3:
                settle(tackler, leave, facing="left" if spot < tackler.x else "right")
            tackler.run(*near, heading)
        elif start_line is not None:
            near = _side_point(hit, target_z - 0.3, tackler.x, tackler.z, 2.4)
            settle(tackler, released or 0.0, facing=facing)
            tackler.run_by(*near, meet - 0.45, choice, facing)
        else:
            near = _side_point(hit, target_z - 0.3, tackler.x, tackler.z, 2.4)
            _close(play, tackler, *near, meet - 0.45, meet - 3.0, facing, placed=True)
        _wrap_toward(tackler, hit, target_z, pile=(spot - hit, down_z - z, drive))


# A kick specialist shows the slot for his job on the play, such as a punter who also holds.
_ROLE_SLOTS = {
    "punter": ("P",),
    "kicker": ("PK",),
    "holder": ("H",),
    "snapper": ("LS",),
    "returner": ("PR", "KR"),
}


def _shown_position(play: _Play, espn_id: str | None, role: str, side: str) -> str | None:
    codes = play.positions.get(espn_id or "", ())
    slot = next((code for code in _ROLE_SLOTS.get(role, ()) if code in codes), None)
    return slot or play.position(espn_id, side) or play.position(espn_id)


def _moments(play: _Play) -> tuple[float, float]:
    """The last moment anything is drawn, and when the play is over: its last movement, or a
    player going down, whichever is later. Players lying on the turf, getting up or shifting their
    weight afterwards aren't the play."""
    ends = [seg.end for *_, t, _ in play.actors for seg in t.segments]
    ends += [seg.end for seg in play.ball if seg.end < 1e8]  # a thrown-away ball may land last
    ends += [prop.land for prop in play.props]
    segments = [seg for *_, t, _ in play.actors for seg in t.segments]
    moved = [
        seg.end
        for seg in segments
        if (seg.x0, seg.z0) != (seg.x1, seg.z1) and not seg.pose.startswith(("idle_", "stance_"))
    ]
    moved += [seg.start for seg in segments if seg.pose.startswith(("ground", "kneel"))]
    moved += [seg.end for seg in play.ball if seg.state == "flight" and seg.end < 1e8]
    return max(ends), round(min(max(moved, default=max(ends)), max(ends)), 4)


def _finish(play: _Play, template: str | None = None, caption: str | None = None) -> PlayScript:
    facts = play.facts
    drawn_until, whistle = _moments(play)
    if play.timed and play.budget is not None:
        # Built to the real time: the whistle is the real one, after a natural dead ball. If even
        # the least plan runs past it, the play finishes naturally after it (OWN-052).
        whistle = round(max(whistle, SNAP + play.budget), 4)
    duration = round(max(drawn_until, whistle) + 1.6, 3)
    actors = []
    for key, espn_id, role, side, track, facing in play.actors:
        last = track.segments[-1]
        if (
            (last.pose in ("stand", IDLE, STANCE) or last.pose in CYCLES)
            and duration - track.t > 0.3
            and role != "official"
        ):
            settle(track, duration, "idle")  # done with the play: idle weight shifts to the end
        segments = [
            s.model_copy(update={"end": min(s.end, duration)})
            for s in track.segments
            if s.start < duration
        ]
        last = segments[-1]
        if last.end < duration:
            segments.append(
                last.model_copy(
                    update={"start": last.end, "end": duration, "x0": last.x1, "z0": last.z1}
                )
            )
        actors.append(
            Actor(
                key=key,
                espn_id=espn_id,
                role=role,
                side=side,  # type: ignore[arg-type]
                label=play.labels.get(key) or (_label(play, role, espn_id) if espn_id else None),
                position=_shown_position(play, espn_id, role, side),
                facing=facing,  # type: ignore[arg-type]
                segments=tuple(segments),
            )
        )
    ball = tuple(
        seg.model_copy(update={"end": min(seg.end, duration)})
        for seg in sorted(play.ball, key=lambda s: s.start)
    )
    lines = [Line(kind="scrimmage", x=play.los)]
    if facts.line_to_gain is not None and facts.line_to_gain < 100:
        lines.append(Line(kind="to_gain", x=float(facts.line_to_gain)))
    return PlayScript(
        event_id=facts.event_id,
        provider_id=facts.provider_id,
        seed=play.seed,
        template=template or facts.template or "",
        duration=duration,
        whistle=whistle,
        offense=facts.offense,
        defense=facts.defense,
        actors=tuple(actors),
        ball=ball,
        lines=tuple(lines),
        caption=caption or _caption(facts),
        note=play.note,
        props=tuple(sorted(play.props, key=lambda prop: prop.start)),
    )


def _label(play: _Play, role: str, espn_id: str) -> str | None:
    """The roster's name for this player. Without one, the text's, but only for a role that names
    exactly one player, since ESPN doesn't list participants in the text's order."""
    if espn_id in play.names:
        return play.names[espn_id]
    if role in ("tackler", "assistedBy"):
        ids, names = (
            play.ids("tackler") + play.ids("assistedBy"),
            play.text_names.get("tackler", []),
        )
    elif role == "interceptor":
        ids, names = (
            play.ids("returner") or play.ids("passDefender"),
            play.text_names.get("interceptor", []),
        )
    else:
        ids, names = play.ids(role), play.text_names.get(role, [])
    return names[0] if len(set(ids)) == 1 and len(names) == 1 else None


# A second word ("A.St. Brown") has lowercase letters, so "A.Barner INTERCEPTED" stops at Barner.
_NAME = r"[A-Z][a-z]{0,3}\.[A-Z][A-Za-z'\-]*(?:\.? [A-Z][a-z][A-Za-z'\-]*)?"
# A sentence ends at a period after a word, a number or a parenthesis, never after an initial,
# so "S.Darnold" and "A.St. Brown" stay whole and "TOUCHDOWN. J.Myers" splits.
_SENTENCE = r"(?:(?<=[A-Za-z]{3})|(?<=[0-9)]))\.\s*(?=[A-Z(])"


def _body(text: str) -> str:
    """The play's own words: no formation, no eligibility report, no direct-snap note."""
    body = re.sub(r"^(?:\([^)]*\)\s*)+", "", text)
    body = re.sub(r"^(?:.*? reported in as eligible\.\s*)+", "", body)  # names hold periods
    body = re.sub(r"^\([^)]*\)\s*", "", body)
    return re.sub(rf"^Direct snap to {_NAME}\.\s*", "", body)


def _text_names(text: str) -> dict[str, list[str]]:
    """Names as the play text writes them, by role."""
    body = _body(text)
    found: dict[str, list[str]] = {}
    lead = re.match(rf"({_NAME}) ", body)
    if lead:
        found["passer"] = found["rusher"] = found["kicker"] = found["punter"] = [lead.group(1)]
    sentences = re.split(_SENTENCE, body)
    if re.search(r"\b(?:punts|kicks)\b", sentences[0]):
        fair = re.search(rf"fair catch by ({_NAME})", body)
        back = len(sentences) > 1 and re.match(
            rf"({_NAME}) (?:to|pushed ob|ran ob|for|MUFFS)\b", sentences[1]
        )
        if fair or back:
            found["returner"] = [(fair or back).group(1)]  # type: ignore[union-attr]
    target = re.search(
        rf"\b(?:pass(?: incomplete)?(?: (?:short|deep) \w+)? (?:to|intended for)) ({_NAME})", body
    )
    if target:
        found["receiver"] = [target.group(1)]
    picked = re.search(rf"INTERCEPTED by ({_NAME})", body)
    if picked:
        found["interceptor"] = [picked.group(1)]
    for sentence in reversed(re.split(_SENTENCE, body)[-3:]):  # the tackle is in the last sentence
        group = re.findall(r"\(([^()]*)\)", sentence)
        if group:
            names = [
                n.strip() for n in re.split(r"[;,]", group[-1]) if re.fullmatch(_NAME, n.strip())
            ]
            if names:
                found.setdefault("tackler", names)
                found.setdefault("sackedBy", names)
                found.setdefault("passDefender", names)
    return found


CAPTION = 140  # characters: what fits on the caption bar's one line beside the re-creation note


def fit(*parts: str) -> str:
    """Join caption parts with a dot. If that runs long, tacklers' names in parentheses go first,
    then a kick unit's snapper and holder, then the spot in the first sentence when its yards
    say the same ("to CHI 21 for 8 yards"), then the end of the text."""
    text = " · ".join(part for part in parts if part)
    for spare, count in (
        (r"\s*\([^()]*\)", 0),
        (r", (?:Center|Holder)-[^,.·]*(?:\.[^,.·\s]+)?", 0),
        (r" (?:to|at) [A-Z]{2,3} -?\d+(?= for )", 1),
    ):
        if len(text) > CAPTION:
            text = re.sub(spare, "", text, count=count)
    return text if len(text) <= CAPTION else text[: CAPTION - 1].rstrip(" ,·") + "…"


def _caption(facts: PlayFacts) -> str:
    sentences = re.split(_SENTENCE, _body(facts.text))
    body = sentences[0].rstrip(".")
    if facts.template in ("punt", "kickoff") and len(sentences) > 1:
        # The return is the kick's second sentence: "T.Horton to SEA 46 for 3 yards (J.Walker)".
        back = sentences[1].rstrip(".")
        if re.match(rf"{_NAME} (?:to|pushed ob|ran ob|for|MUFFS)\b", back):
            body = f"{body}. {back}"
    clock = f"Q{facts.period} {facts.clock}" if facts.period and facts.clock else ""
    down = ""
    if facts.down and facts.distance is not None:
        nth = {1: "1st", 2: "2nd", 3: "3rd", 4: "4th"}[facts.down]
        goal = facts.line_to_gain is not None and facts.line_to_gain >= 100
        down = f"{nth} & {'Goal' if goal else facts.distance}"
    if facts.template in ("punt", "kickoff"):
        return fit(clock, down, body)
    return " · ".join(part for part in (clock, down, body[:120]) if part)
