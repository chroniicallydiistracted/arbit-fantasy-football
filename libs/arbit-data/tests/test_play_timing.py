"""Runs built to their real snap-to-whistle time (OWN-051, OWN-052): the whistle is the real one,
the time comes from more football at natural speeds, and nothing reads as slow motion."""

import math

from arbit_data.live.choreography import (
    CYCLES,
    MOMENTUM,
    SLOWEST_RUN,
    SNAP,
    PlayScript,
    choreograph,
)
from live_cases import facts

AFTER = ("idle_", "stance_", "stand", "rise")


def build(name: str, real: float | None) -> PlayScript:
    made = choreograph(facts(name), f"{name}:timing", real_seconds=real)
    assert made is not None
    return made


def action_end(script: PlayScript) -> float:
    """When the play is over: the last movement of the play or a player going down."""
    moments = [SNAP]
    for actor in script.actors:
        previous = None
        for seg in actor.segments:
            if math.hypot(seg.x1 - seg.x0, seg.z1 - seg.z0) > 0.05 and not seg.pose.startswith(
                AFTER
            ):
                moments.append(seg.end)
            # Going down, not lying there: the script continues a last pose to its end.
            if seg.pose.startswith(("ground", "kneel")) and previous != seg.pose:
                moments.append(seg.start)
            previous = seg.pose
    moments += [b.end for b in script.ball if b.state == "flight"]
    return max(moments)


def speed(seg) -> float:
    seconds = seg.end - seg.start
    return math.hypot(seg.x1 - seg.x0, seg.z1 - seg.z0) / seconds if seconds > 0 else 0.0


def test_a_run_slower_than_ours_ends_on_the_real_whistle_after_a_natural_dead_ball():
    natural = build("run_gap", None)
    real = natural.whistle - SNAP + 2.5
    timed = build("run_gap", real)
    assert timed.whistle == round(SNAP + real, 4)
    assert 0.4 - 1e-6 <= timed.whistle - action_end(timed) <= 1.5 + 1e-6


def test_the_added_time_is_football_at_natural_speeds():
    timed = build("run_gap", build("run_gap", None).whistle - SNAP + 2.5)
    rusher = next(a for a in timed.actors if a.role == "rusher")
    runs = [speed(s) for s in rusher.segments if s.pose == "RUN" and s.end - s.start > 0.25]
    assert runs and min(runs) >= SLOWEST_RUN
    pile = [s for s in rusher.segments if s.pose in ("drive", "stumble") and s.start > SNAP]
    assert sum(s.end - s.start for s in pile) > 0.5, "contact and a drive to the spot"
    assert all(speed(s) >= 0.45 for s in pile), "a pile always moves"
    for actor in timed.actors:
        for seg in actor.segments:
            limit = 11.0 if seg.pose in CYCLES else MOMENTUM.get(seg.pose, 1.5)
            assert speed(seg) <= limit + 1e-6, (actor.key, seg.pose)


def test_the_run_still_ends_on_the_spot():
    natural = build("run_gap", None)
    timed = build("run_gap", natural.whistle - SNAP + 2.5)

    def down_at(script: PlayScript) -> float:
        rusher = next(a for a in script.actors if a.role == "rusher")
        return next(s.x0 for s in rusher.segments if s.pose == "ground")

    assert down_at(timed) == down_at(natural)


def test_the_same_play_is_timed_the_same_way_every_time():
    real = build("run_gap", None).whistle - SNAP + 1.7
    assert build("run_gap", real) == build("run_gap", real)


def test_a_scramble_faster_than_ours_takes_back_its_look_in_the_pocket():
    natural = build("scramble", None)
    ours = action_end(natural) - SNAP
    timed = build("scramble", ours - 0.3)
    assert action_end(timed) < action_end(natural) - 0.25


def test_without_a_real_time_the_run_keeps_its_natural_timing():
    natural = build("run_gap", None)
    assert natural.whistle == round(action_end(natural), 4)
