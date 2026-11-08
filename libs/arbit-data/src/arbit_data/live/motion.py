"""Replacement motion plans fitted to PBP landmarks, independent of private tracking."""

from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
from math import dist, pi
from random import Random
from typing import Literal

from arbit_data.live import alignment
from arbit_data.live.actions import ActionKind, ActionPerson, ActionSequence, ActionStep, Confidence
from arbit_data.live.choreography import FIELD_WIDTH, HASHES, LABEL, SNAP, BallEnd, Line, Units
from arbit_data.live.contracts import LiveModel
from arbit_data.live.play_facts import PlayFacts
from arbit_data.live.timing import Fitted, Phase, fit
from arbit_data.live.trajectory import MotionAnchor, MotionKey, path, within_speed

Point = tuple[float, float]
BallStyle = Literal["rest", "snap", "exchange", "held", "pass", "kick", "bounce", "roll"]


class PoseCue(LiveModel):
    start: float
    pose: str


class MotionActor(LiveModel):
    key: str
    espn_id: str | None = None
    label: str | None = None
    side: Literal["offense", "defense", "official"]
    role: str
    track: tuple[MotionKey, ...]
    poses: tuple[PoseCue, ...]


class MotionBall(LiveModel):
    start: float
    end: float
    style: BallStyle
    origin: BallEnd
    target: BallEnd | None = None


class Milestone(LiveModel):
    kind: ActionKind
    t: float
    confidence: Confidence = "estimated"


class MotionTiming(LiveModel):
    provider_seconds: float | None = None
    overrun: float
    unfilled: float


class PlayScriptV2(LiveModel):
    version: Literal[2] = 2
    event_id: str
    provider_id: str
    template: str
    duration: float
    whistle: float
    motion_end: float
    offense: str | None
    defense: str | None
    actors: tuple[MotionActor, ...]
    ball: tuple[MotionBall, ...]
    milestones: tuple[Milestone, ...]
    timing: MotionTiming
    lines: tuple[Line, ...]
    caption: str
    label: str = LABEL
    note: str | None = None


@dataclass(frozen=True)
class MotionContext:
    facts: PlayFacts
    names: Mapping[str, str]
    positions: Mapping[str, tuple[str, ...]]
    units: Units


def _anchor(t: float, point: Point, heading: float | None = None) -> MotionAnchor:
    return MotionAnchor(t=t, x=point[0], z=point[1], heading=heading)


def _actor(
    person: ActionPerson,
    role: str,
    points: list[MotionAnchor],
    poses: list[tuple[float, str]],
    side: Literal["offense", "defense"] = "offense",
) -> MotionActor:
    return MotionActor(
        key=person.key,
        espn_id=person.espn_id,
        label=person.name,
        role=role,
        side=side,
        track=path(points),
        poses=tuple(PoseCue(start=t, pose=pose) for t, pose in poses),
    )


def _specialist(context: MotionContext, team: str, role: str) -> ActionPerson | None:
    unit = context.units.get(team, {}).get(role)
    if unit is None:
        return None
    espn_id, name = unit
    return ActionPerson(
        key=f"espn:{espn_id}",
        espn_id=espn_id,
        team_id=team,
        name=context.names.get(espn_id) or name,
        roles=(role,),
    )


def _lane(z: float) -> float:
    return min(FIELD_WIDTH - 1.0, max(1.0, z))


def _carry_path(
    mesh: Point, end_x: float, los: float, z: float, side: int, gap: float, score: bool
) -> list[Point]:
    gain = end_x - los
    if gain <= 0.5:
        return [mesh, (end_x, _lane(z + side * (1.5 + gap * 0.35)))]
    hole = (los + min(0.4, gain * 0.25), _lane(z + side * gap))
    if gain < 9:
        return [mesh, hole, (end_x, _lane(hole[1] + 0.8 * side))]
    # Move through the reported gap before opening up into the run.
    widen = min(16.0 if score else 9.0, gain * 0.25) if side else 0.0
    bend = (los + gain * 0.42, _lane(hole[1] + side * widen * 0.75))
    return [mesh, hole, bend, (end_x, _lane(hole[1] + side * widen))]


def _carry_anchors(points: list[Point], start: float, finish: float) -> list[MotionAnchor]:
    weights = [max(0.15, dist(a, b)) for a, b in zip(points, points[1:], strict=False)]
    total = sum(weights)
    traversed = 0.0
    out = []
    for weight, point in zip(weights, points[1:], strict=True):
        traversed += weight
        out.append(_anchor(start + (finish - start) * traversed / total, point))
    return out


def _toward(a: Point, b: Point, yards: float) -> Point:
    length = dist(a, b)
    if length < 1e-6:
        return b
    return a[0] + (b[0] - a[0]) * yards / length, a[1] + (b[1] - a[1]) * yards / length


def _cross_goal(points: list[MotionAnchor], direction: int) -> float:
    """Leave the scoring anchor moving, then decelerate inside the end zone."""
    goal = points[-1]
    # Tracking has the scoring carrier typically another 2–3 yards away 0.4 s later.
    finish = goal.t + 0.86
    drift = max(-1.4, min(1.4, goal.z - points[-2].z))
    x = max(-10.0, min(110.0, goal.x + 3.7 * direction))
    points.append(_anchor(finish, (x, _lane(goal.z + drift))))
    return finish


def _pursuit(
    person: ActionPerson,
    start: Point,
    target: Point,
    react: float,
    meet: float,
    side: Literal["offense", "defense"] = "defense",
    facing: float = pi,
    approach: str = "drive",
) -> MotionActor | None:
    """Read the play on moving feet, then close the last yards at the carrier's spot."""
    elapsed = meet - react
    gap = dist(start, target)
    if elapsed < 0.25 or gap > 9.0 * (elapsed - 0.12):
        return None
    # At long windows, spend the extra time reading the play before the downhill break.
    close = min(elapsed * 0.82, max(0.28, gap / 7.7 + 0.22))
    read_end = meet - close
    read = _toward(start, target, min(gap * 0.36, (read_end - react) * 2.5))
    # Continue into the wrap so the defender still has momentum at first contact.
    through = _toward(target, start, -min(0.52, gap * 0.18))
    actor = _actor(
        person,
        "tackler",
        [
            _anchor(react, start, facing),
            _anchor(read_end, read),
            _anchor(meet, target),
            _anchor(meet + 0.28, through),
        ],
        [
            (0, "stance_1"),
            (react, approach),
            (read_end, "RUN"),
            (meet - 0.10, "lunge"),
            (meet, "wrap"),
            (meet + 0.28, "ground"),
        ],
        side,
    )
    return actor if within_speed(actor.track, 11.0) else None


PREVIEW_SHAPES = frozenset({"run", "pass", "interception", "kickoff"})


def _pick(actions: ActionSequence, kind: ActionKind) -> ActionStep | None:
    return next((step for step in actions.steps if step.kind == kind), None)


def _person(actions: ActionSequence, key: str | None) -> ActionPerson | None:
    return next((person for person in actions.people if person.key == key), None)


def _credited_contact(actions: ActionSequence, facts: PlayFacts) -> tuple[str, ...]:
    contact = _pick(actions, "contact")
    if contact is None or facts.touchdown or facts.out_of_bounds:
        return ()
    return (
        tuple(dict.fromkeys((contact.actor, *contact.actors))) if contact.actor else contact.actors
    )


def _finish_clock(
    actions: ActionSequence,
    fitted: Fitted,
    motion_end: float,
    origin: float = SNAP,
    *,
    live_end: float | None = None,
) -> tuple[float, float, MotionTiming]:
    provider = actions.duration.value
    whistle = (
        round(origin + provider, 6)
        if provider is not None
        else (motion_end if live_end is None else live_end) + fitted.seconds["dead"]
    )
    return (
        whistle,
        max(motion_end, whistle) + 1.6,
        MotionTiming(
            provider_seconds=provider,
            overrun=fitted.over,
            unfilled=fitted.unfilled,
        ),
    )


def _output(
    actions: ActionSequence,
    facts: PlayFacts,
    fitted: Fitted,
    actors: list[MotionActor],
    ball: list[MotionBall],
    milestones: list[Milestone],
    motion_end: float,
    *,
    origin: float = SNAP,
    note: str | None = None,
    live_end: float | None = None,
) -> PlayScriptV2:
    whistle, duration, timing = _finish_clock(
        actions, fitted, motion_end, origin, live_end=live_end
    )
    milestones.append(
        Milestone(
            kind="dead",
            t=whistle,
            confidence="derived" if timing.provider_seconds is not None else "estimated",
        )
    )
    assert facts.start is not None
    lines = [Line(kind="scrimmage", x=float(facts.start))]
    if facts.line_to_gain is not None and facts.line_to_gain < 100:
        lines.append(Line(kind="to_gain", x=float(facts.line_to_gain)))
    return PlayScriptV2(
        event_id=actions.event_id,
        provider_id=actions.play_id,
        template=actions.shape,
        duration=duration,
        whistle=whistle,
        motion_end=motion_end,
        offense=facts.offense,
        defense=facts.defense,
        actors=tuple(actors),
        ball=tuple(ball),
        milestones=tuple(sorted(milestones, key=lambda m: m.t)),
        timing=timing,
        lines=tuple(lines),
        caption=facts.text,
        note=note,
    )


def plan(actions: ActionSequence, context: MotionContext) -> PlayScriptV2 | None:
    """Build a replacement plan when the action family and its anchors are supported."""
    if actions.cancelled or context.facts.reason is not None or context.facts.penalties:
        return None
    contact = _pick(actions, "contact")
    if actions.shape == "kickoff" and contact and len(contact.actors) > 1:
        return (
            None  # Keep the existing shared-tackle clip until the new solver can place each player.
        )
    if actions.shape in ("pass", "interception"):
        from arbit_data.live.motion_pass import passing

        built = passing(actions, context)
    elif actions.shape == "kickoff":
        from arbit_data.live.motion_kick import kickoff

        built = kickoff(actions, context)
    else:
        built = _run(actions, context) if actions.shape == "run" else None
    if built is not None and any(not within_speed(actor.track, 11.0) for actor in built.actors):
        return None
    return built


def _run(actions: ActionSequence, context: MotionContext) -> PlayScriptV2 | None:
    facts = context.facts
    if facts.start is None or facts.offense is None or facts.run is None or facts.fumble:
        return None
    people = {p.key: p for p in actions.people}
    advance = next((s for s in actions.steps if s.kind == "advance" and s.actor), None)
    if advance is None or advance.actor not in people:
        return None
    carrier = people[advance.actor]
    if facts.direct_snap and (carrier.name or "").casefold() != facts.direct_snap.casefold():
        # A snap to one player and run by another needs an extra exchange.
        return None
    center = _specialist(context, facts.offense, "center")
    quarterback = _specialist(context, facts.offense, "quarterback")
    codes = context.positions.get(carrier.espn_id or "", ())
    carrier_position = alignment.pick(codes, "offense")
    direct = (
        carrier_position == "QB"
        or facts.direct_snap is not None
        or (quarterback is not None and quarterback.key == carrier.key)
    )
    if not direct and quarterback is None:
        return None

    los = float(facts.start)
    end_x = 100.0 if facts.touchdown else advance.spot.value
    if end_x is None and facts.yards is not None and not facts.penalties:
        end_x = los + facts.yards
    if end_x is None or not -10 <= end_x <= 100:
        return None
    rng = Random(
        int.from_bytes(
            sha256(f"{actions.event_id}/{actions.play_id}/run".encode()).digest()[:8], "big"
        )
    )
    z = rng.choice(HASHES)
    side = -1 if facts.run.side == "left" else 1 if facts.run.side == "right" else 0
    gap = {"end": 7.0, "tackle": 3.7, "guard": 1.9}.get(facts.run.gap or "", 0.0)
    qb_start = (los - (5.0 if facts.shotgun else 1.25), z)
    back_side = -side if side else rng.choice((-1, 1))
    start = (
        qb_start
        if direct
        else (
            los - (5.25 if facts.shotgun else 7.0),
            _lane(z + (1.7 * back_side if facts.shotgun else 0.0)),
        )
    )
    mesh = (los - (3.8 if facts.shotgun else 3.4), _lane(z + 0.65 * (side or 1)))
    if direct:
        mesh = (qb_start[0] + 0.2, qb_start[1])
    points = _carry_path(mesh, end_x, los, z, side, gap, facts.touchdown)
    if facts.out_of_bounds:
        points[-1] = (
            end_x,
            0.0 if side < 0 or (side == 0 and z < FIELD_WIDTH / 2) else FIELD_WIDTH,
        )
    length = sum(dist(a, b) for a, b in zip(points, points[1:], strict=False))
    # Leave time to accelerate and finish at the spot. Most additional time comes from
    # the approach, exchange and contact instead of stretching a sprint indefinitely.
    gain_time = max(0.34, length / 8.6 + 0.28)
    mesh_phase = (
        Phase("mesh", 0.30, 0.42, 0.8)
        if direct
        else Phase("mesh", 0.90, 1.15, 1.45)
        if facts.shotgun
        else Phase("mesh", 0.98, 1.26, 1.60)
    )
    credit = _credited_contact(actions, facts)
    contact_path = list(points)
    if credit and dist(points[-2], points[-1]) > 1.1:
        contact_path[-1] = _toward(points[-1], points[-2], 0.9)
    drives = bool(credit) and contact_path[-1] != points[-1]
    fitted = fit(
        (
            mesh_phase,
            Phase("gain", gain_time, gain_time + 0.19, gain_time + 0.34),
            Phase("contact", 0.27, 0.40, 0.85) if drives else Phase("contact", 0, 0, 0),
            Phase("dead", 0.0, 0.12, 0.4),
        ),
        actions.duration.value,
    )
    exchange = SNAP + fitted.seconds["mesh"]
    boundary = exchange + fitted.seconds["gain"]
    terminal = boundary + fitted.seconds["contact"]
    carrier_points = [
        _anchor(SNAP, start, 0.0),
        _anchor(exchange, mesh),
        *_carry_anchors(contact_path, exchange, boundary),
    ]
    if drives:
        carrier_points.append(_anchor(terminal, points[-1]))
    motion_end = _cross_goal(carrier_points, 1) if facts.touchdown else terminal
    _, duration, _ = _finish_clock(actions, fitted, motion_end, live_end=terminal)
    actors = [
        _actor(
            carrier,
            "rusher",
            carrier_points,
            [
                (0.0, "ready"),
                (SNAP, "RUN"),
                (exchange - 0.08, "take"),
                (min(exchange + 0.14, boundary), "RUN"),
                (motion_end, "arms_up" if facts.touchdown else "idle_1"),
            ],
        ),
    ]
    snap_end = SNAP + (0.28 if facts.shotgun else 0.12)
    take_snap = carrier if direct else quarterback
    assert take_snap is not None
    if not direct:
        actors.append(
            _actor(
                take_snap,
                "quarterback",
                [
                    _anchor(SNAP, qb_start, 0.0),
                    _anchor(exchange, (mesh[0] - 0.45, mesh[1] - 0.7)),
                    _anchor(exchange + 0.55, (mesh[0] - 0.6, mesh[1] - 1.1), 0.0),
                ],
                [
                    (0, "ready"),
                    (snap_end, "DROP"),
                    (exchange - 0.18, "handoff_give"),
                    (exchange + 0.04, "handoff_follow"),
                    (exchange + 0.55, "idle_1"),
                ],
            )
        )
    if center is not None and center.key not in {a.key for a in actors}:
        release = max(snap_end + 0.16, SNAP + 0.46)
        actors.append(
            _actor(
                center,
                "snapper",
                [
                    _anchor(release, (los - 0.45, z), 0.0),
                    _anchor(release + 0.75, (los + 0.65, _lane(z + 0.55 * side)), 0.0),
                ],
                [
                    (0, "snap_ready"),
                    (SNAP, "snap_release"),
                    (release, "drive"),
                    (release + 0.75, "idle_1"),
                ],
            )
        )

    carrier_hold = BallEnd(actor=carrier.key, hold="chest")
    qb_hold = carrier_hold if direct else BallEnd(actor=take_snap.key, hold="hand")
    ball_start = BallEnd(point=(los, 0.16, z))
    balls = [
        MotionBall(start=0, end=SNAP, style="rest", origin=ball_start),
        MotionBall(start=SNAP, end=snap_end, style="snap", origin=ball_start, target=qb_hold),
    ]
    milestones = [Milestone(kind="snap", t=SNAP)]
    if not direct:
        balls.extend(
            (
                MotionBall(start=snap_end, end=exchange - 0.09, style="held", origin=qb_hold),
                MotionBall(
                    start=exchange - 0.09,
                    end=exchange,
                    style="exchange",
                    origin=qb_hold,
                    target=carrier_hold,
                ),
            )
        )
        milestones.append(Milestone(kind="exchange", t=exchange))
    balls.append(
        MotionBall(
            start=snap_end if direct else exchange, end=duration, style="held", origin=carrier_hold
        )
    )

    drawn: set[str] = set()
    on_field = {actor.key for actor in actors}
    contact_at = contact_path[-1]
    setup = alignment.Context(los, z, facts.shotgun, "run", side)
    for index, actor_key in enumerate(credit):
        tackler = people.get(actor_key)
        if tackler is None or actor_key in on_field or actor_key in drawn:
            continue
        code = alignment.pick(context.positions.get(tackler.espn_id or "", ()), "defense")
        set_at = alignment.spot(code or "", setup, toward=contact_at[1])
        start_def = (
            (max(los + 0.7, set_at[0]), _lane(set_at[1]))
            if set_at
            else (los + 4.0, _lane(z + (side or -1) * 3.0))
        )
        sign = 1 if start_def[1] >= contact_at[1] else -1
        if index % 2:
            sign = -sign
        end_def = (contact_at[0] + 0.55, _lane(contact_at[1] + sign * (0.65 + 0.2 * index)))
        pursuer = _pursuit(tackler, start_def, end_def, SNAP + 0.16, boundary + 0.08 * len(drawn))
        if pursuer:
            actors.append(pursuer)
            drawn.add(actor_key)
    if drawn:
        actors[0] = actors[0].model_copy(
            update={
                "poses": (
                    *actors[0].poses[:-1],
                    PoseCue(start=boundary, pose="hit"),
                    PoseCue(start=boundary + 0.15, pose="stumble"),
                    PoseCue(start=max(boundary + 0.22, terminal - 0.14), pose="fall_30"),
                    PoseCue(start=max(boundary + 0.34, terminal), pose="ground"),
                ),
            }
        )
        milestones.append(Milestone(kind="contact", t=boundary))
    if facts.touchdown or facts.out_of_bounds:
        milestones.append(
            Milestone(kind="score" if facts.touchdown else "out_of_bounds", t=boundary)
        )
    note = None
    if any(key not in drawn for key in credit):
        note = "Some credited contact could not be inferred from the available play details."
    return _output(
        actions, facts, fitted, actors, balls, milestones, motion_end, live_end=terminal, note=note
    )
