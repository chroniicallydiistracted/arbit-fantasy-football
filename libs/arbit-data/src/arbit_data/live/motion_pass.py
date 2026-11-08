"""Phase and path planning for the pass and interception previews."""

from math import dist, pi

from arbit_data.live import alignment
from arbit_data.live.actions import ActionPerson, ActionSequence
from arbit_data.live.choreography import FIELD_WIDTH, SNAP, BallEnd
from arbit_data.live.motion import (
    Milestone,
    MotionActor,
    MotionBall,
    MotionContext,
    PlayScriptV2,
    Point,
    _actor,
    _anchor,
    _carry_anchors,
    _credited_contact,
    _cross_goal,
    _finish_clock,
    _lane,
    _output,
    _person,
    _pick,
    _pursuit,
    _specialist,
    _toward,
)
from arbit_data.live.timing import Phase, fit
from arbit_data.live.trajectory import MotionAnchor


def _start(
    context: MotionContext,
    person: ActionPerson,
    setup: alignment.Context,
    defense: bool,
    lane: float,
) -> Point:
    side = "defense" if defense else "offense"
    position = alignment.pick(context.positions.get(person.espn_id or "", ()), side)
    if alignment.group(position) in ("CB", "NB"):
        depth = 3.6 if setup.shotgun else 3.0
        return setup.los + depth, _lane(lane)
    if not defense and alignment.group(position) in ("WR", None):
        # Wideouts split wider than the typical pass arrival lane. The pass
        # direction supplies the side, while the route brings them to the ball.
        split = 14.0 if setup.side else 8.0
        return setup.los - 0.65, _lane(setup.ball_z + (setup.side or 1) * split)
    spot = alignment.spot(position or "", setup, toward=lane)
    if spot:
        return spot[0], _lane(spot[1])
    return setup.los + (3.2 if defense else -0.65), _lane(lane)


def _receiver_route(start: Point, end: Point, depth: str | None) -> list[Point]:
    """Infer a stem and break. A pass behind the line calls for a flat or screen release."""
    dx, dz = end[0] - start[0], end[1] - start[1]
    if dx <= 1.5:
        stem = (start[0] + min(1.6, dx * 0.28), _lane(start[1] + dz * 0.54))
    else:
        stem = (start[0] + min(10.0, dx * 0.56), _lane(start[1] + dz * 0.18))
    # A short throw to nearly the same spot still needs a release and a turn back.
    if depth == "short" and dist(start, end) < 8 and dx > -2:
        stem = (max(start[0] + 3.2, end[0] - 1.6), _lane(start[1] - (2.2 if dz >= 0 else -2.2)))
    return [start, stem, end]


def _route_points(
    route: list[Point], begin: float, arrival: float, *, moving_catch: bool
) -> list[MotionAnchor]:
    start, stem, end = route
    if arrival - begin < 1.1 or dist(start, stem) < 1.3:
        return [_anchor(begin, start), *_carry_anchors(route, begin, arrival)]
    first_step = _toward(start, stem, 1.05)
    step_at = begin + 0.65
    approach = [first_step, stem, end]
    if moving_catch and end[0] - start[0] > 2.6 and end[0] - stem[0] < 2.4:
        # Round the break so the receiver can finish downfield instead of turning
        # ninety degrees at the catch.
        approach.insert(-1, (end[0] - 1.7, end[1]))
    return [
        _anchor(begin, start),
        _anchor(step_at, first_step),
        *_carry_anchors(approach, step_at, arrival),
    ]


def passing(actions: ActionSequence, context: MotionContext) -> PlayScriptV2 | None:
    facts = context.facts
    passing = facts.passing
    if facts.start is None or not facts.offense or not passing or facts.fumble:
        return None
    released = _pick(actions, "release")
    arrived = _pick(actions, "arrival")
    caught = _pick(actions, "possession")
    if released is None or arrived is None:
        return None
    qb = _person(actions, released.actor)
    receiver = _person(actions, released.target)
    carrier = _person(actions, caught.actor) if caught else None
    picked = passing.result == "intercepted"
    if qb is None or (caught is not None and carrier is None):
        return None

    los = float(facts.start)
    z = 23.58 if passing.side == "left" else 29.75 if passing.side == "right" else FIELD_WIDTH / 2
    side = -1 if passing.side == "left" else 1 if passing.side == "right" else 0
    depth: float | None = arrived.spot.value
    if depth is None and actions.air_yards.value is not None:
        depth = los + actions.air_yards.value
    if depth is None:
        return None
    if not -9 <= depth <= 109:
        return None
    catch_at = (float(depth), _lane(z + side * (10.0 if passing.depth == "deep" else 7.5)))
    qb_start = (los - (5.0 if facts.shotgun else 1.25), z)
    pocket = (qb_start[0] - (1.8 if facts.shotgun else 3.6), _lane(z + side * 0.9))
    alignment_setup = alignment.Context(los, z, facts.shotgun, "pass", side)
    target_spot = _lane(catch_at[1] + (side or 1) * 1.3)
    route: list[Point] = []
    if receiver:
        start = _start(context, receiver, alignment_setup, False, target_spot)
        finish = catch_at if not picked else (catch_at[0] + 1.05, target_spot)
        route = _receiver_route(start, finish, passing.depth)
    pick_start = (
        _start(context, carrier, alignment_setup, True, catch_at[1]) if picked and carrier else None
    )
    route_length = sum(dist(a, b) for a, b in zip(route, route[1:], strict=False))
    distance = dist(pocket, catch_at)
    # Horizontal ball displacement in yards per second. Height is a separate
    # visual estimate. Use a narrow flight window so the play clock cannot slow
    # the pass itself to absorb time.
    air_time = max(0.24, distance / (20.0 if passing.depth == "deep" else 19.6))
    flight = Phase("flight", air_time * 0.91, air_time, air_time * 1.10)
    min_release = max(1.25 if facts.shotgun else 1.50, route_length / 7.8 + 0.58 - flight.least)
    if pick_start:
        min_release = max(min_release, dist(pick_start, catch_at) / 7.5 + 0.24 - flight.least)
    if min_release > 5.2:
        return None
    deep = passing.depth == "deep"
    natural_release = max(min_release, 3.3 if deep else 2.5)
    max_release = 4.65 if deep else 3.15 if picked else 3.55
    release = Phase("release", min_release, natural_release, max(natural_release, max_release))
    advance = _pick(actions, "advance")
    end_x: float | None = advance.spot.value if advance else None
    if carrier and facts.touchdown:
        end_x = min(0.0, catch_at[0]) if picked else max(100.0, catch_at[0])
    if end_x is None:
        end_x = catch_at[0]
    finish_z = catch_at[1]
    if carrier and facts.out_of_bounds:
        finish_z = 0.0 if catch_at[1] < FIELD_WIDTH / 2 else FIELD_WIDTH
    elif carrier and abs(end_x - catch_at[0]) > 8:
        finish_z = _lane(catch_at[1] + (side or 1) * min(7.0, abs(end_x - catch_at[0]) * 0.22))
    finish_at = (float(end_x), finish_z)
    yac = dist(catch_at, finish_at)
    credit = _credited_contact(actions, facts) if carrier else ()
    contact_at = _toward(finish_at, catch_at, 0.8) if credit and yac > 1.7 else finish_at
    drive = contact_at != finish_at
    carry_distance = dist(catch_at, contact_at)
    carry_time = max(0.23, carry_distance / 8.1 + 0.19) if carrier else 0.0
    phases = [
        release,
        flight,
        Phase("carry", carry_time, carry_time + 0.12, carry_time + 0.28)
        if carrier
        else Phase("carry", 0, 0, 0),
        Phase("contact", 0.28, 0.40, 0.75) if drive else Phase("contact", 0, 0, 0),
        Phase("dead", 0.0, 0.15, 0.55),
    ]
    fitted = fit(phases, actions.duration.value)
    thrown = SNAP + fitted.seconds["release"]
    arrival = thrown + fitted.seconds["flight"]
    boundary = arrival + fitted.seconds["carry"]
    possession = arrival + 0.11 if carrier else arrival
    terminal = boundary + fitted.seconds["contact"]
    # A catch in the end zone scores at possession, then the receiver runs through.
    score_at = possession if yac < 0.05 else boundary
    motion_end = score_at + 0.86 if facts.touchdown and carrier else terminal
    _, duration, _ = _finish_clock(
        actions, fitted, motion_end, live_end=score_at if facts.touchdown else terminal
    )

    def finish_carry(points: list[MotionAnchor]) -> None:
        if yac > 0.05:
            points.append(_anchor(boundary, contact_at))
            if drive:
                points.append(_anchor(terminal, finish_at))
        if facts.touchdown:
            if yac <= 0.05:
                direction = -1 if picked else 1
                entry = points[-1]
                # For an end-zone catch preserve the actual inferred arrival spot.
                points.append(_anchor(score_at, (entry.x + 0.42 * direction, entry.z)))
            _cross_goal(points, -1 if picked else 1)

    snap_end = SNAP + (0.28 if facts.shotgun else 0.12)
    set_time = min(thrown - 0.47, snap_end + 0.83)
    reset_time = (set_time + thrown) * 0.5
    actors: list[MotionActor] = [
        _actor(
            qb,
            "passer",
            [
                _anchor(SNAP, qb_start, 0.0),
                _anchor(set_time, pocket, 0.0),
                _anchor(reset_time, (pocket[0] - 0.35, _lane(pocket[1] + 0.36)), 0.0),
                _anchor(thrown, (pocket[0] + 0.36, pocket[1]), 0.0),
                _anchor(thrown + 0.44, (pocket[0] + 0.7, pocket[1]), 0.0),
            ],
            [
                (0, "ready"),
                (snap_end, "DROP"),
                (set_time, "DROP"),
                (thrown - 0.29, "throw_cock"),
                (thrown - 0.11, "throw_mid"),
                (thrown - 0.02, "throw_rel"),
                (thrown + 0.07, "throw_follow"),
                (thrown + 0.44, "idle_1"),
            ],
        ),
    ]
    center = _specialist(context, facts.offense, "center")
    if center and center.key != qb.key:
        actors.append(
            _actor(
                center,
                "snapper",
                [
                    _anchor(SNAP + 0.27, (los - 0.45, z), 0.0),
                    _anchor(SNAP + 0.98, (los - 1.45, _lane(z + side * 0.50)), 0.0),
                ],
                [
                    (0, "snap_ready"),
                    (SNAP, "snap_release"),
                    (SNAP + 0.27, "DROP"),
                    (SNAP + 0.98, "stance_1"),
                    (thrown + 0.4, "idle_1"),
                ],
            )
        )
    drawn: set[str] = set()
    if receiver and route and receiver.key not in {actor.key for actor in actors}:
        begin = SNAP + 0.06
        points = _route_points(
            route,
            begin,
            arrival,
            moving_catch=bool(carrier and receiver.key == carrier.key and yac > 1.5),
        )
        poses = [(0.0, "stance_1"), (begin, "RUN")]
        if carrier and receiver.key == carrier.key:
            poses.extend(((arrival - 0.13, "catch_reach"), (possession, "catch_secure")))
            finish_carry(points)
            if yac > 1.5 or facts.touchdown:
                poses.append((min(possession + 0.15, motion_end - 0.01), "RUN"))
            poses.append((motion_end, "arms_up" if facts.touchdown else "idle_1"))
        elif receiver.key in credit:
            meet = (contact_at[0] + 0.45, _lane(contact_at[1] + (side or 1) * 0.5))
            if boundary - arrival > max(0.22, dist(route[-1], meet) / 7.4 + 0.10):
                points.append(_anchor(boundary, meet))
                points.append(_anchor(boundary + 0.26, _toward(meet, route[-1], -0.38)))
                poses.extend(
                    ((boundary - 0.11, "lunge"), (boundary, "wrap"), (boundary + 0.30, "ground"))
                )
                drawn.add(receiver.key)
        if receiver.key != (carrier.key if carrier else None) and receiver.key not in drawn:
            # A missed target takes another step after the ball goes by.
            after = _toward(route[-1], route[-2], -1.15)
            points.append(_anchor(arrival + 0.42, (after[0], _lane(after[1]))))
            poses.append((arrival + 0.42, "idle_1"))
        actors.append(_actor(receiver, "receiver", points, poses))

    if picked and carrier and pick_start:
        drop = (min(108.0, pick_start[0] + 2.0), _lane(pick_start[1] + (side or 1) * 0.7))
        pickup = SNAP + 0.17
        drop_at = pickup + min(0.86, (arrival - pickup) * 0.42)
        points = [
            _anchor(pickup, pick_start, pi),
            _anchor(drop_at, drop, pi),
            _anchor(arrival, catch_at, pi),
        ]
        finish_carry(points)
        poses = [
            (0, "stance_1"),
            (pickup, "BACKPEDAL"),
            (drop_at, "RUN"),
            (arrival - 0.13, "catch_reach"),
            (possession, "catch_secure"),
        ]
        if yac > 1.5 or facts.touchdown:
            poses.append((min(possession + 0.15, motion_end - 0.01), "RUN"))
        poses.append((motion_end, "arms_up" if facts.touchdown else "idle_1"))
        actors.append(_actor(carrier, "interceptor", points, poses, "defense"))

    if carrier and not any(actor.key == carrier.key for actor in actors):
        return None
    on_field = {actor.key for actor in actors}
    defender_side = not picked
    for index, key in enumerate(credit):
        tackler = _person(actions, key)
        if tackler is None or key in on_field:
            continue
        flank = (side or 1) * (-1 if index % 2 else 1)
        start = _start(context, tackler, alignment_setup, defender_side, finish_z + 2 * flank)
        meet = (
            contact_at[0] + (0.45 if defender_side else -0.45),
            _lane(contact_at[1] + flank * (0.6 + index * 0.2)),
        )
        pursuer = _pursuit(
            tackler,
            start,
            meet,
            SNAP + 0.17,
            boundary + 0.08 * len(drawn),
            "defense" if defender_side else "offense",
            pi if defender_side else 0.0,
            "BACKPEDAL" if defender_side and meet[0] > start[0] else "drive",
        )
        if pursuer:
            actors.append(pursuer)
            drawn.add(key)

    if drawn and carrier:
        index = next(i for i, actor in enumerate(actors) if actor.key == carrier.key)
        actor = actors[index]
        cue = actor.poses[-1].model_copy
        actors[index] = actor.model_copy(
            update={
                "poses": (
                    *(pose for pose in actor.poses if pose.start < boundary),
                    cue(update={"start": boundary, "pose": "hit"}),
                    cue(update={"start": boundary + 0.16, "pose": "stumble"}),
                    cue(update={"start": max(boundary + 0.26, terminal - 0.12), "pose": "fall_30"}),
                    cue(update={"start": max(boundary + 0.38, terminal), "pose": "ground"}),
                ),
            }
        )
    ball_start = BallEnd(point=(los, 0.16, z))
    in_hand = BallEnd(actor=qb.key, hold="hand")
    target = (
        BallEnd(actor=carrier.key, hold="hands")
        if carrier
        else BallEnd(point=(catch_at[0], 0.12, catch_at[1]))
    )
    balls = [
        MotionBall(start=0, end=SNAP, style="rest", origin=ball_start),
        MotionBall(start=SNAP, end=snap_end, style="snap", origin=ball_start, target=in_hand),
        MotionBall(start=snap_end, end=thrown, style="held", origin=in_hand),
        MotionBall(start=thrown, end=arrival, style="pass", origin=in_hand, target=target),
    ]
    if carrier and yac > 1.5 and boundary > possession + 0.18:
        tucked = BallEnd(actor=carrier.key, hold="chest")
        tuck_at = possession + 0.16
        balls.extend(
            (
                MotionBall(start=arrival, end=possession, style="held", origin=target),
                MotionBall(
                    start=possession, end=tuck_at, style="exchange", origin=target, target=tucked
                ),
                MotionBall(start=tuck_at, end=duration, style="held", origin=tucked),
            )
        )
    else:
        balls.append(
            MotionBall(
                start=arrival, end=duration, style="held" if carrier else "rest", origin=target
            )
        )
    events = [
        Milestone(kind="snap", t=SNAP),
        Milestone(kind="release", t=thrown),
        Milestone(kind="arrival", t=arrival),
    ]
    if carrier:
        events.append(Milestone(kind="possession", t=possession))
    if drawn:
        events.append(Milestone(kind="contact", t=boundary))
    if facts.touchdown:
        events.append(Milestone(kind="score", t=score_at))
    elif facts.out_of_bounds:
        events.append(Milestone(kind="out_of_bounds", t=boundary))
    note = (
        "The credited contact could not be timed within the reconstructed paths."
        if any(key not in drawn for key in credit)
        else None
    )
    return _output(
        actions,
        facts,
        fitted,
        actors,
        balls,
        events,
        motion_end,
        live_end=score_at if facts.touchdown else terminal,
        note=note,
    )
