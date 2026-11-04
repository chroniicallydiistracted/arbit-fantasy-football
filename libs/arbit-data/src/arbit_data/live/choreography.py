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

import hashlib
import math
import random
import re
from collections.abc import Mapping
from typing import Literal

from arbit_data.live.contracts import LiveModel
from arbit_data.live.play_facts import PlayFacts

FIELD_WIDTH = 160 / 3
HASHES = (23.58, 29.75)  # NFL hash marks, 70 ft 9 in from each sideline
SNAP = 0.6  # seconds of set before the snap
TOP_SPEED = 9.2  # yards a second, about 19 mph
CYCLES = frozenset({"RUN", "DROP"})
# Poses that carry a body's momentum through contact or a catch, and how fast they may travel.
MOMENTUM = {
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
    "slide": 7.0,
}
STILL = 1.5  # yards a second: the most a standing pose may drift
SLOWEST_RUN = 5.5  # yards a second: below this the run cycle reads as slow motion
LONGEST_STILL = 0.6  # seconds a standing pose may hold without a step, except before the snap
LABEL = "Re-creation from play-by-play"
TEMPLATES = frozenset({"pass", "interception", "sack", "run", "scramble", "kneel"})
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
    espn_id: str
    role: str
    side: Literal["offense", "defense"]
    label: str | None = None
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


class PlayScript(LiveModel):
    version: Literal[1] = 1
    event_id: str
    provider_id: str
    seed: str
    template: str
    duration: float
    offense: str | None
    defense: str | None
    actors: tuple[Actor, ...]
    ball: tuple[BallSegment, ...]
    lines: tuple[Line, ...]
    caption: str
    label: str = LABEL


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
    else:
        frames, step, rise, sway = ("ready", "drop_b", "ready", "drop_c"), 0.3, 0.0, 0.22
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


class _Play:
    """Shared state while one play is choreographed."""

    def __init__(self, facts: PlayFacts, seed: str, names: Mapping[str, str]):
        self.facts = facts
        self.seed = seed
        self.rng = random.Random(int.from_bytes(hashlib.sha256(seed.encode()).digest()[:8], "big"))
        self.los = float(facts.start or 0)
        self.end = float(facts.action_end if facts.action_end is not None else facts.end or 0)
        self.z = self.rng.uniform(*HASHES)
        self.actors: list[tuple[str, str, str, str, _Track, str]] = []
        self.ball: list[BallSegment] = []
        self.names = names
        self.text_names = _text_names(facts.text)

    def ids(self, role: str) -> list[str]:
        return list(dict.fromkeys(p.espn_id for p in self.facts.players if p.role == role))

    def track(self, x: float, z: float, kind: str) -> _Track:
        return _Track(x, z, self.rng.uniform(*_SPEEDS[kind]))

    def add(
        self, key: str, espn_id: str, role: str, side: str, track: _Track, facing: str
    ) -> _Track:
        self.actors.append((key, espn_id, role, side, track, facing))
        return track

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
        if end - start > 1e-6:
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
    facts: PlayFacts, seed: str, names: Mapping[str, str] | None = None
) -> PlayScript | None:
    """A script for the play, or None when its facts have no template here or miss a fact.
    `names` gives display names by ESPN ID, from the rosters; the text fills in only a role that
    names exactly one player."""
    if facts.template not in TEMPLATES or facts.missing or facts.start is None:
        return None
    play = _Play(facts, seed, names or {})
    if facts.template == "kneel" or (facts.run and facts.run.style == "kneel"):
        built: _Play | None = None if facts.end is None else _kneel(play)
    elif facts.template == "pass" and facts.passing:
        built = None if facts.passing.result == "spiked" else _pass(play)
    elif facts.template == "interception":
        built = _interception(play)
    elif facts.template == "sack":
        built = _sack(play)
    elif facts.template in ("run", "scramble"):
        built = _run(play)
    else:
        built = None
    return _finish(built) if built else None


# The quarterback -----------------------------------------------------------------------------


def _snap(play: _Play, key: str, espn_id: str, role: str, start_x: float, shotgun: bool) -> _Track:
    """A quarterback (or a back taking a direct snap) sets and takes the snap."""
    track = play.add(
        key, espn_id, role, "offense", play.track(start_x, play.z, "quarterback"), "right"
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
        play.los - (5.0 if facts.shotgun else 1.0),
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
    receiver = play.add(
        "receiver",
        receivers[0],
        "receiver",
        "offense",
        play.track(start_x, start_z, "receiver"),
        "right",
    )
    receiver.hold("ready", SNAP + 0.1)
    if deep:
        # Through the catch: the ball meets him in stride.
        reach = receiver.speed * 0.27
        receiver.run(catch_x - reach, catch_z)
        catch_t = receiver.t + 0.27
        flight = _flight(play, catch_x, catch_z, qb_x, air)
        release = catch_t - flight
        if release < earliest:  # he'd be there before the ball could be: a longer, bending route
            extra = (earliest - release) * receiver.speed
            receiver.segments.clear()
            receiver.t, receiver.x, receiver.z = 0.0, start_x, start_z
            receiver.hold("ready", SNAP + 0.1)
            bend = math.hypot(catch_x - reach - start_x, catch_z - start_z) + extra
            receiver.run(
                *_waypoint(
                    (start_x, start_z), (catch_x - reach, catch_z), bend, play.rng.choice((-1, 1))
                )
            )
            receiver.run(catch_x - reach, catch_z)
            catch_t = receiver.t + 0.27
            release = catch_t - flight
        reach_e, reach_pose = (
            ("catch_high_e", "catch_high") if air >= 20 else ("catch_reach_e", "catch_reach")
        )
        receiver.move(reach_e, 0.15, catch_x - reach * 0.45, catch_z).move(
            reach_pose, 0.12, catch_x, catch_z
        )
    else:
        # To his spot, a step past the catch; he settles facing the quarterback and comes back.
        receiver.run(catch_x + 0.7, catch_z)
        flight = _flight(play, catch_x, catch_z, qb_x, air)
        release = max(earliest, receiver.t + 0.27 + play.rng.uniform(0.15, 0.5) - flight)
        catch_t = release + flight
        settle(receiver, catch_t - 0.27, facing="left")
        receiver.move("catch_reach_e", 0.15, catch_x + 0.35, catch_z, "left")
        receiver.move("catch_reach", 0.12, catch_x, catch_z, "left")
    _throw(qb, release)
    play.release("passer", release)
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
    receiver.move(
        "catch_secure",
        0.2,
        catch_x + (receiver.speed * 0.2 if deep and ahead else 0.4 if ahead else 0.0),
        catch_z,
    )
    _carry(play, receiver, "receiver", catch_z, way=1)
    return play


def _incomplete(play: _Play, release: float, catch_t: float, x: float, z: float) -> _Play:
    """The ball reaches the target and falls past him, or a defender gets a hand on it."""
    receiver = play.find("receiver")
    receiver.hold("stand", 0.3)
    landing = (x + play.rng.uniform(1.0, 3.0), 0.12, z + play.rng.uniform(-1.5, 1.5))
    defenders = play.ids("passDefender")
    if defenders:
        defender = play.add(
            "defender",
            defenders[0],
            "passDefender",
            "defense",
            play.track(x + 7.0, z + 2.5, "defense"),
            "left",
        )
        _close(play, defender, x + 0.9, z + 0.5, catch_t - 0.2, react=release - 0.6)
        defender.move("lunge", 0.2, x + 0.6, z + 0.4).hold("stand", 0.3)
    play.fly(release, catch_t + 0.12, BallEnd(actor="passer", hold="hand"), BallEnd(point=landing))
    play.rest(catch_t + 0.12, 1e9, landing)
    return play


def _interception(play: _Play) -> _Play | None:
    facts = play.facts
    passing = facts.passing
    assert passing is not None and passing.catch_spot is not None
    pickers = play.ids("returner") or play.ids("passDefender")
    if not pickers:
        return None
    pick_x, pick_z = float(passing.catch_spot), play.lane(passing.side)
    air = pick_x - play.los
    steps = _steps_for(air)
    qb = _snap(
        play,
        "passer",
        play.ids("passer")[0],
        "passer",
        play.los - (5.0 if facts.shotgun else 1.0),
        facts.shotgun,
    )
    _drop(play, qb, steps)
    release = max(qb.t + 0.55, SNAP + play.rng.uniform(1.9, 2.6))
    catch_t = release + _flight(play, pick_x, pick_z, qb.x, air)
    _throw(qb, release)
    play.release("passer", release)
    picker = play.add(
        "interceptor",
        pickers[0],
        "interceptor",
        "defense",
        play.track(pick_x + 5.0, pick_z + 3.0, "defense"),
        "left",
    )
    _close(play, picker, pick_x + 0.6, pick_z, catch_t - 0.37, react=SNAP + 0.3)
    picker.hold("catch_high_e", 0.25).hold("catch_high", 0.12)
    play.fly(
        release,
        catch_t,
        BallEnd(actor="passer", hold="hand"),
        BallEnd(actor="interceptor", hold="hands"),
    )
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
        play.los - (5.0 if facts.shotgun else 1.0),
        facts.shotgun,
    )
    spot = play.end
    drop_to = spot + 0.6  # where the hit lands: ESPN's spot is where he went down
    qb.move("DROP", max(0.3, abs(qb.x - drop_to) / play.rng.uniform(3.2, 3.8)), drop_to, play.z)
    contact = max(qb.t + 0.5, SNAP + play.rng.uniform(2.2, 3.0))
    rushers = play.ids("sackedBy")[:2]
    plans = []
    for index, espn_id in enumerate(rushers):
        side = 1 if index == 0 else -1
        start = (play.los + 1.0, play.z + side * play.rng.uniform(3.0, 7.0))
        track = play.track(*start, "defense")
        plans.append((espn_id, track, side))
        # A rusher who would arrive late makes the quarterback wait a little longer.
        straight = math.hypot(spot + 2.4 - start[0], play.z - start[1])
        contact = max(contact, SNAP + 0.15 + straight / track.speed + 0.45)
    settle(qb, contact - 0.13, "pocket", climb=False)  # he's caught where he set
    qb.move("hit_back", 0.1, spot + 0.3, qb.z).move("fall_back_30", 0.12, spot + 0.1, qb.z)
    qb.move("fall_back_60", 0.15, spot, qb.z).hold("ground_back", 0.3)
    for index, (espn_id, track, side) in enumerate(plans):
        rusher = play.add(f"sacker_{index + 1}", espn_id, "sackedBy", "defense", track, "left")
        rusher.hold("ready", SNAP + 0.15)
        # Around the edge: a longer path at his own pace, not a slow straight one.
        rusher.run_by(spot + 2.4, play.z + 0.3 * side, contact + 0.06 * index - 0.45, side)
        _wrap(rusher, spot + 0.3, play.z + 0.3 * side, side=1)
    return play


def _kneel(play: _Play) -> _Play:
    rusher = (play.ids("rusher") or play.ids("passer"))[0]
    track = play.add(
        "rusher",
        rusher,
        "rusher",
        "offense",
        play.track(play.los - 0.4, play.z, "quarterback"),
        "right",
    )
    track.hold("ready", SNAP)
    play.rest(0.0, SNAP, (play.los, 0.15, play.z))
    play.hold_ball("rusher", SNAP)
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
            play.los - (5.0 if facts.shotgun else 1.0),
            facts.shotgun,
        )
        _drop(play, qb, 3)
        settle(qb, qb.t + play.rng.uniform(0.7, 1.3), "pocket")
        out = min(FIELD_WIDTH - 3.0, max(3.0, play.z + sign * play.rng.uniform(4.0, 9.0)))
        qb.run(max(qb.x, play.los - 3.0), out)
        _carry(play, qb, "rusher", out, way=1)
        return play
    if style == "sneak":
        qb = _snap(play, "rusher", rusher, "rusher", play.los - 1.0, False)
        # A push in the pile: the drive pose, at a pile's pace.
        qb.move("drive", max(0.4, (play.end - qb.x) / 3.0), play.end, play.z).hold("ground", 0.3)
        return play
    back = 5.0 if facts.shotgun else 7.0
    start_z = play.z + (play.rng.choice((-1.5, 1.5)) if facts.shotgun else 0.0)
    track = play.add(
        "rusher",
        rusher,
        "rusher",
        "offense",
        play.track(play.los - back, start_z, "rusher"),
        "right",
    )
    track.hold("ready", SNAP + 0.1)
    play.rest(0.0, SNAP, (play.los, 0.15, play.z))
    handoff = SNAP + 0.55
    play.fly(
        SNAP, handoff, BallEnd(point=(play.los, 0.3, play.z)), BallEnd(actor="rusher", hold="chest")
    )
    play.hold_ball("rusher", handoff)
    if play.end > play.los + 1:
        track.run(play.los + 0.3, hole_z)
    _carry(play, track, "rusher", hole_z, way=1)
    return play


# Shared pieces --------------------------------------------------------------------------------


def _close(
    play: _Play,
    track: _Track,
    x: float,
    z: float,
    arrive: float,
    react: float,
    facing: str | None = None,
) -> None:
    """Get a defender to (x, z) at `arrive`, at his own pace. A new one starts where he could
    plausibly have been and sets there with a side step until he breaks; one already on the
    field runs from where he is."""
    react = max(react, track.t)
    if not track.segments:
        sprint = min(play.rng.uniform(1.0, 1.8), max(0.3, arrive - react))
        reach = min(
            track.speed * sprint, math.hypot(track.x - x, track.z - z) or track.speed * sprint
        )
        angle = math.atan2(track.z - z, track.x - x)
        track.x = x + reach * math.cos(angle)
        track.z = min(FIELD_WIDTH - 1.0, max(1.0, z + reach * math.sin(angle)))
        settle(track, arrive - math.hypot(track.x - x, track.z - z) / track.speed, facing=facing)
        track.run(x, z, facing)
        return
    track.run_by(x, z, arrive, play.rng.choice((-1, 1)), facing)


def _wrap(track: _Track, spot: float, z: float, side: int, facing: str | None = None) -> None:
    """The hand-made tackler's finish (`real_plays.tackler`): lunge, wrap, drive, fall, get up."""
    track.move("lunge", 0.2, spot + 1.1 * side, z - 0.2, facing).move(
        "wrap", 0.15, spot + 0.5 * side, z - 0.2, facing
    )
    track.move("drive", 0.1, spot + 0.3 * side, z - 0.2, facing).move(
        "fall_60", 0.2, spot + 0.2 * side, z - 0.2, facing
    )
    track.hold("ground", 1.4, facing).hold("rise_1", 0.3, facing).hold("rise_2", 0.3, facing)
    track.hold("rise_3", 0.3, facing).hold("ready", 0.3, facing)


def _carry(play: _Play, track: _Track, key: str, lane_z: float, way: int) -> None:
    """Run the ball to ESPN's spot at the carrier's own pace and end the play there: tackled, out
    of bounds or in the end zone. If a tackler can't get there in time, the carrier weaves."""
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
        return
    if facts.out_of_bounds:
        track.run(spot, 0.6 if lane_z < FIELD_WIDTH / 2 else FIELD_WIDTH - 0.6)
        track.hold("stand", 0.3)
        return
    z = min(FIELD_WIDTH - 2.0, max(2.0, lane_z + rng.uniform(-3.0, 3.0)))
    before = spot - way * 0.7
    running = way * (before - track.x) > 0.3
    if not running:  # no ground left to gain: absorb it where he is, in his lane
        z = track.z
    reach = math.hypot(before - track.x, z - track.z)
    contact = (
        track.t + (reach / track.speed if running else max(0.2, abs(track.x - before) / 3.0)) + 0.13
    )
    tacklers = list(dict.fromkeys(play.ids("tackler") + play.ids("assistedBy")))[:3]
    drawn = {espn_id: (t, k) for k, espn_id, *_, t, _ in play.actors}
    for espn_id in tacklers:
        if espn_id in drawn and drawn[espn_id][1] != key:
            # Already on the field, such as a passer tackling the interceptor: he chases from where
            # he is, at his pace, and the carrier weaves so he can get there.
            chaser = drawn[espn_id][0]
            gap = math.hypot(chaser.x - (spot - way * 2.4), chaser.z - z)
            contact = max(contact, chaser.t + gap / chaser.speed + 0.45)
    if running:
        track.run_by(before, z, contact - 0.13, rng.choice((-1, 1)), wait_first=False)
    elif abs(track.x - before) > 0.05:
        track.move("stumble", max(0.2, abs(track.x - before) / 3.0), before, z)
        settle(track, contact - 0.13)
    track.move("hit", 0.1, spot - way * 0.4, z).move("stumble", 0.1, spot - way * 0.25, z)
    track.move("fall_30", 0.1, spot - way * 0.1, z).move("fall_60", 0.15, spot, z).hold(
        "ground", 0.3
    )
    toward = "right" if way > 0 else "left"
    for index, espn_id in enumerate(tacklers):
        offset = (0.0, 1.6, -1.6)[index]
        role = "tackler" if index == 0 else "assistedBy"
        meet = contact + 0.08 * index
        if espn_id in drawn and drawn[espn_id][1] != key:
            chaser = drawn[espn_id][0]
            chaser.run_by(
                spot - way * 2.4, z + offset - 0.3, meet - 0.45, rng.choice((-1, 1)), toward
            )
            _wrap(chaser, spot, z + offset, -way, toward)
            continue
        behind = key == "interceptor"  # after a pick the offense chases from behind the return
        side_x = -way if behind else way
        tackler = play.add(
            f"tackler_{index + 1}",
            espn_id,
            role,
            "offense" if behind else "defense",
            play.track(
                spot + side_x * rng.uniform(7.0, 13.0), z + rng.uniform(-8.0, 8.0), "defense"
            ),
            toward if behind else ("left" if way > 0 else "right"),
        )
        facing = toward if behind else None
        _close(
            play, tackler, spot + side_x * 2.4, z + offset - 0.3, meet - 0.45, meet - 3.0, facing
        )
        _wrap(tackler, spot + way * 0.1 * index * (0 if behind else 1), z + offset, side_x, facing)


def _finish(play: _Play) -> PlayScript:
    facts = play.facts
    ends = [seg.end for *_, t, _ in play.actors for seg in t.segments]
    ends += [seg.end for seg in play.ball if seg.end < 1e8]  # a thrown-away ball may land last
    duration = round(max(ends) + 1.6, 3)
    actors = []
    for key, espn_id, role, side, track, facing in play.actors:
        last = track.segments[-1]
        if last.pose in ("stand", "ready") and duration - track.t > 0.3:
            settle(track, duration)  # standing: keep a natural side step to the end
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
                label=_label(play, role, espn_id),
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
        template=facts.template or "",
        duration=duration,
        offense=facts.offense,
        defense=facts.defense,
        actors=tuple(actors),
        ball=ball,
        lines=tuple(lines),
        caption=_caption(facts),
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


_NAME = r"[A-Z][a-z]{0,3}\.[A-Z][A-Za-z'\-]*(?:\.? [A-Z][A-Za-z'\-]+)?"
# A sentence ends at a period after a word, a number or a parenthesis, never after an initial,
# so "S.Darnold" and "A.St. Brown" stay whole and "TOUCHDOWN. J.Myers" splits.
_SENTENCE = r"(?:(?<=[A-Za-z]{3})|(?<=[0-9)]))\.\s*(?=[A-Z(])"


def _body(text: str) -> str:
    """The play's own words: no formation, no eligibility report, no direct-snap note."""
    body = re.sub(r"^(?:\([^)]*\)\s*)+", "", text)
    body = re.sub(r"^(?:.*? reported in as eligible\.\s*)+", "", body)  # names hold periods
    return re.sub(r"^\([^)]*\)\s*", "", body)


def _text_names(text: str) -> dict[str, list[str]]:
    """Names as the play text writes them, by role."""
    body = _body(text)
    found: dict[str, list[str]] = {}
    lead = re.match(rf"({_NAME}) ", body)
    if lead:
        found["passer"] = found["rusher"] = [lead.group(1)]
    target = re.search(
        rf"\b(?:pass(?: incomplete)? (?:short|deep) \w+ (?:to|intended for)) ({_NAME})", body
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


def _caption(facts: PlayFacts) -> str:
    body = re.split(_SENTENCE, _body(facts.text))[0].rstrip(".")
    clock = f"Q{facts.period} {facts.clock}" if facts.period and facts.clock else ""
    down = ""
    if facts.down and facts.distance is not None:
        nth = {1: "1st", 2: "2nd", 3: "3rd", 4: "4th"}[facts.down]
        goal = facts.line_to_gain is not None and facts.line_to_gain >= 100
        down = f"{nth} & {'Goal' if goal else facts.distance}"
    return " · ".join(part for part in (clock, down, body[:120]) if part)
