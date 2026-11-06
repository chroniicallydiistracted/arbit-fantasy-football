"""Pace a play to its real snap-to-whistle time (OWN-041).

The NFL API gives each play's snap and whistle times. Arbit's plays animate faster than the real
ones: on CHI at SEA, runs in about 0.53 of the real time and passes in 0.63. The owner's direction
is to change movement and timing first and keep how running and throwing look, so nothing reads
as slow motion:

1. **The action slows by one factor after the snap.** The quarterback holds the ball longer and
   throws later, and every pose and flight takes longer by the same factor. Players stay where
   they were going, so a runner covers less ground each second.
2. **The factor stops where motion would look slow.** No run falls below the slowest pace a run
   cycle reads as running (5.5 yards a second), no held pose stretches past what reads as frozen,
   the handoff stays right after the snap (OWN-037), and a short burst at another pace stays
   short. A run's stride follows its ground speed, so a slower run is a slower stride, never a
   slowed-down film.
3. **The rest of the real time is the end of the play.** The whistle comes at the real time.
   Players who are done shift their weight in idle as they do after any play, those on the
   turf stay there, and the board's clock runs to the whistle.

A play the NFL timed faster than Arbit's keeps Arbit's timing, and a play without real times is
unchanged.
"""

import math

from arbit_data.live.choreography import (
    CYCLES,
    LONGEST_STILL,
    MOMENTUM,
    SLOWEST_RUN,
    SNAP,
    BallSegment,
    PlayScript,
    Segment,
)

MOST = 2.0  # never more than twice as slow
RUN_FLOOR = SLOWEST_RUN + 0.05  # a little above the floor, so rounding never crosses it
HANDOFF_BY = SNAP + 0.9  # the run's handoff comes right after the snap (OWN-037)
SHORT_RUN = 0.25  # a run this short isn't a pace of its own
WAIT = 0.5  # seconds of each weight shift in a wait
# Poses a player may hold as long as the play needs (as the rule check has them).
RESTING = ("ground", "rise", "kneel", "point", "arms", "spike", "hold_", "recover", "snap_", "off_")
WAITING = ("idle_", "stance_")


def _speed(seg: Segment) -> float:
    seconds = seg.end - seg.start
    return math.hypot(seg.x1 - seg.x0, seg.z1 - seg.z0) / seconds if seconds > 0 else 0.0


def slowest(script: PlayScript) -> float:
    """How far the action may slow before something would look wrong."""
    limit = MOST
    for actor in script.actors:
        after = [s for s in actor.segments if s.end > SNAP and s.end > s.start]
        paces = [_speed(s) for s in after if s.pose == "RUN" and s.end - s.start > SHORT_RUN]
        # A run begun before the snap (jet motion) keeps its pace, so the run after it may slow
        # only as far as one pace allows (0.15 yards a second, as the rule check has it).
        before = [
            _speed(s)
            for s in actor.segments
            if s.pose == "RUN" and s.start < SNAP - 1e-6 and s.end - s.start > SHORT_RUN
        ]
        for early in before:
            for pace_after in paces:
                if early - 0.15 > 0:
                    limit = min(limit, pace_after / (early - 0.15))
        for seg in after:
            seconds = seg.end - seg.start
            if seg.pose == "RUN":
                speed = _speed(seg)
                if speed > 0:
                    limit = min(limit, speed / RUN_FLOOR)
                # A short burst at another pace (a break on the ball) stays short, so it never
                # becomes a pace change.
                runs = [_speed(r) for r in after if r.pose == "RUN"]
                if seconds <= SHORT_RUN + 1e-6 and max(runs) - min(runs) > 0.15:
                    limit = min(limit, SHORT_RUN / seconds)
            elif (
                seg.pose not in CYCLES
                and seg.pose not in MOMENTUM
                and not seg.pose.startswith(RESTING + WAITING)
                and seconds <= LONGEST_STILL + 1e-6
            ):
                limit = min(limit, LONGEST_STILL / seconds)
    for held in script.ball:
        if held.state == "held" and held.actor and SNAP < held.start <= HANDOFF_BY:
            carrier = next((a for a in script.actors if a.key == held.actor), None)
            if carrier is not None and carrier.role in ("rusher",):
                limit = min(limit, (HANDOFF_BY - SNAP) / max(1e-3, held.start - SNAP))
    return max(1.0, limit)


def _waits(segments: list[Segment]) -> list[Segment]:
    """A wait longer than a still pose may hold becomes weight shifts between its two poses."""
    out: list[Segment] = []
    for seg in segments:
        seconds = seg.end - seg.start
        if not seg.pose.startswith(WAITING) or seconds <= LONGEST_STILL or seg.end <= SNAP:
            out.append(seg)
            continue
        family = seg.pose.rsplit("_", 1)[0]
        pieces = math.ceil(seconds / WAIT)
        for i in range(pieces):
            a, b = i / pieces, (i + 1) / pieces
            out.append(
                seg.model_copy(
                    update={
                        "start": round(seg.start + seconds * a, 6),
                        "end": round(seg.start + seconds * b, 6),
                        "pose": f"{family}_{1 + i % 2}",
                        "x0": seg.x0 + (seg.x1 - seg.x0) * a,
                        "z0": seg.z0 + (seg.z1 - seg.z0) * a,
                        "x1": seg.x0 + (seg.x1 - seg.x0) * b,
                        "z1": seg.z0 + (seg.z1 - seg.z0) * b,
                    }
                )
            )
    return out


def _tail(segments: list[Segment], duration: float) -> list[Segment]:
    """Carry an actor to the end of the paced play: a player on the turf stays down; anyone else
    shifts his weight in idle, as players do after every play."""
    last = segments[-1]
    if last.end >= duration - 1e-6:
        return segments
    if last.pose.startswith(RESTING):
        return [*segments[:-1], last.model_copy(update={"end": duration})]
    out = list(segments)
    pieces = max(
        1, math.ceil((duration - last.end) / WAIT - 1e-9)
    )  # even shifts of half a second at most
    length = (duration - last.end) / pieces
    x, z = last.x1, last.z1
    for i in range(pieces):
        start = last.end + i * length
        step = (0.08 if i % 2 == 0 else -0.08) if length >= 0.4 else 0.0  # a small step in place
        out.append(
            last.model_copy(
                update={
                    "start": round(start, 6),
                    "end": round(duration if i == pieces - 1 else start + length, 6),
                    "pose": f"idle_{1 + i % 2}",
                    "x0": x,
                    "z0": z,
                    "x1": x,
                    "z1": z + step,
                }
            )
        )
        z += step
    return out


def pace(script: PlayScript, real_seconds: float | None) -> PlayScript:
    """The script with its action slowed toward `real_seconds` from snap to whistle, and its
    whistle at the real time."""
    ours = script.whistle - SNAP
    if real_seconds is None or real_seconds <= 0 or ours <= 0 or real_seconds <= ours:
        return script
    factor = min(real_seconds / ours, slowest(script))

    def at(t: float) -> float:
        return round(t if t <= SNAP else SNAP + (t - SNAP) * factor, 6)

    old_end = script.duration
    whistle = round(max(at(script.whistle), SNAP + real_seconds), 6)
    duration = round(max(whistle + (old_end - script.whistle), at(old_end)), 6)

    actors = []
    for actor in script.actors:
        moved = [
            seg.model_copy(update={"start": at(seg.start), "end": at(seg.end)})
            for seg in actor.segments
        ]
        # The script's own closing hold ended at its old end; the paced play ends later.
        actors.append(actor.model_copy(update={"segments": tuple(_tail(_waits(moved), duration))}))

    balls = []
    for i, seg in enumerate(script.ball):
        last = i == len(script.ball) - 1 and seg.end >= old_end - 1e-6
        balls.append(
            seg.model_copy(
                update={"start": at(seg.start), "end": duration if last else at(seg.end)}
            )
        )
    props = tuple(
        p.model_copy(update={"start": at(p.start), "land": at(p.land)}) for p in script.props
    )
    return script.model_copy(
        update={
            "actors": tuple(actors),
            "ball": tuple(balls),
            "props": props,
            "whistle": whistle,
            "duration": duration,
        }
    )


__all__ = ["BallSegment", "pace", "slowest"]
