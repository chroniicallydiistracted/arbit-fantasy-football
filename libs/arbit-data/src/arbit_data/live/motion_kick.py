"""Kickoff phases follow ordered reception, return and recovery evidence."""

import re
from math import dist, pi

from arbit_data.live.actions import ActionSequence
from arbit_data.live.choreography import FIELD_WIDTH, SNAP, BallEnd
from arbit_data.live.motion import (
    Milestone,
    MotionBall,
    MotionContext,
    PlayScriptV2,
    PoseCue,
    _actor,
    _anchor,
    _carry_anchors,
    _finish_clock,
    _lane,
    _output,
    _person,
    _pick,
    _pursuit,
    _toward,
)
from arbit_data.live.timing import Phase, fit
from arbit_data.live.trajectory import path


def kickoff(actions: ActionSequence, context: MotionContext) -> PlayScriptV2 | None:
    facts = context.facts
    kick = facts.kick
    kicked, landed = _pick(actions, "kick"), _pick(actions, "arrival")
    if not kick or facts.start is None or kicked is None or landed is None:
        return None
    if kick.onside or kick.result not in (
        "returned",
        "fair_catch",
        "touchback",
        "out_of_bounds",
        "recovered",
    ):
        return None
    kicker = _person(actions, kicked.actor)
    caught = _pick(actions, "possession")
    advance = _pick(actions, "advance")
    loose = _pick(actions, "loose")
    recovery = _pick(actions, "recovery")
    receiver = _person(actions, caught.actor) if caught else None
    contact = _pick(actions, "contact")
    tackler = _person(actions, contact.actor) if contact else None
    recoverer = _person(actions, recovery.actor) if recovery else None
    if not kicker or landed.spot.value is None or (caught and receiver is None):
        return None
    if advance and advance.spot.value is None:
        return None

    tee = (float(facts.start), FIELD_WIDTH / 2)
    land_z = FIELD_WIDTH - 0.4 if kick.result == "out_of_bounds" else _lane(tee[1] + 8.0)
    land = (float(landed.spot.value), land_z)
    if not 0 <= land[0] <= 110:
        return None
    end_x = advance.spot.value if advance and advance.spot.value is not None else land[0]
    if not 0 <= end_x <= 110:
        return None
    finish_z = _lane(land_z - min(7.0, abs(land[0] - end_x) * 0.24))
    if facts.out_of_bounds and advance:
        finish_z = FIELD_WIDTH
    finish = (float(end_x), finish_z)
    yards = dist(land, finish)
    carried = yards / 7.7 + 0.24 if advance else 0.0
    hang = min(4.15, max(3.25, 2.75 + dist(tee, land) / 66))
    distance_loose = (
        abs(recovery.spot.value - end_x) if recovery and recovery.spot.value is not None else 1.0
    )
    bounce = min(1.1, 0.42 + distance_loose / 11) if loose else 0.0
    fitted = fit(
        (
            Phase("flight", hang * 0.79, hang, hang * 1.14),
            Phase("return", carried, carried + 0.26, carried + 1.0)
            if advance
            else Phase("return", 0, 0, 0),
            Phase("loose", bounce * 0.85, bounce, bounce * 1.33),
            Phase("dead", 0.0, 0.34, 0.90),
        ),
        actions.duration.value,
    )
    kick_at = SNAP + 0.90
    arrival = kick_at + fitted.seconds["flight"]
    end_return = arrival + fitted.seconds["return"]
    live_end = end_return + fitted.seconds["loose"]
    # The generic "to end zone" description does not establish where it landed
    # or that someone caught it. Show a conservative ground continuation.
    roll = (
        kick.result == "touchback"
        and receiver is None
        and land[0] < 109.5
        and not re.search(
            r"\b(?:(?:through|out of) the end zone|caught|downed|kneels|out of bounds)\b",
            facts.text,
            re.I,
        )
    )
    bounce_end = arrival + 0.30
    motion_end = bounce_end + 0.58 if roll else live_end
    _, duration, _ = _finish_clock(actions, fitted, motion_end, kick_at, live_end=live_end)
    actors = [
        _actor(
            kicker,
            "kicker",
            [
                _anchor(SNAP, (tee[0] - 5.5, tee[1] - 1.65)),
                _anchor(kick_at - 0.20, (tee[0] - 1.55, tee[1] - 0.54)),
                _anchor(kick_at, (tee[0] - 0.85, tee[1] - 0.22)),
                _anchor(kick_at + 0.55, (tee[0] + 0.28, tee[1])),
            ],
            [
                (0, "stance_1"),
                (SNAP, "RUN"),
                (kick_at - 0.20, "kick_plant"),
                (kick_at - 0.09, "kick_strike"),
                (kick_at, "kick_follow"),
                (kick_at + 0.55, "idle_1"),
            ],
        )
    ]
    draw_contact = False
    has_drive = yards > 2.0 and end_return - arrival > 0.55
    contact_time = end_return - 0.32 if has_drive else end_return
    contact_spot = _toward(finish, land, 1.2) if has_drive else finish
    tackle_end = (contact_spot[0] - 0.5, _lane(contact_spot[1] + 0.64))
    recovery_point = (
        float(recovery.spot.value)
        if recovery and recovery.spot.value is not None
        else finish[0] + 0.6,
        _lane(finish_z + 0.48),
    )
    if tackler and advance and tackler.key != kicker.key and not facts.out_of_bounds:
        start_at = (tee[0] + 25.0, _lane(tee[1] + 4.0))
        pursuer = _pursuit(tackler, start_at, tackle_end, arrival, contact_time, "offense", 0.0)
        if pursuer:
            if recoverer and tackler.key == recoverer.key and motion_end > contact_time + 0.30:
                pursuer = pursuer.model_copy(
                    update={
                        "track": path(
                            [
                                *[
                                    _anchor(key.t, (key.x, key.z), key.heading)
                                    for key in pursuer.track[:-1]
                                ],
                                _anchor(end_return, (finish[0] - 0.36, _lane(finish_z + 0.42))),
                                _anchor(motion_end, recovery_point),
                            ]
                        ),
                        "poses": (
                            *pursuer.poses[:-1],
                            PoseCue(start=end_return, pose="drive"),
                            PoseCue(start=motion_end, pose="recover"),
                        ),
                    }
                )
            actors.append(pursuer)
            draw_contact = True
    if receiver:
        ready = (min(110.0, land[0] + 2.2), _lane(land[1] - 1.0))
        adjust = _toward(ready, land, 0.65)
        points = [
            _anchor(max(kick_at, arrival - 1.2), ready, pi),
            _anchor(arrival - 0.42, adjust, pi),
            _anchor(arrival, land, pi),
        ]
        poses = [
            (0.0, "stance_1"),
            (max(kick_at, arrival - 1.2), "drive"),
            (arrival - 0.26, "catch_reach"),
            (arrival + 0.09, "catch_secure"),
        ]
        if advance:
            turn = (land[0] + (end_x - land[0]) * 0.44, _lane(land_z + (finish_z - land_z) * 0.36))
            if draw_contact and has_drive:
                points.extend(_carry_anchors([land, turn, contact_spot], arrival, contact_time))
                points.append(_anchor(end_return, finish))
            else:
                points.extend(_carry_anchors([land, turn, finish], arrival, end_return))
            if end_return > arrival + 0.30:
                poses.append((arrival + 0.26, "RUN"))
            if draw_contact:
                poses.extend(((contact_time, "hit"), (end_return + 0.25, "ground")))
            else:
                poses.append((end_return, "idle_1"))
        else:
            poses.append((arrival + 0.35, "idle_1"))
        if recoverer and receiver.key == recoverer.key and motion_end > end_return:
            points.append(_anchor(motion_end, recovery_point))
            poses.append((motion_end, "recover"))
        actors.append(_actor(receiver, "returner", points, poses, "defense"))
    if recoverer and loose and recoverer.key not in {a.key for a in actors}:
        from_offense = recovery is not None and recovery.team_id == facts.offense
        start = (tee[0] + 25.0 if from_offense else land[0] - 2.0, _lane(land_z - 3.0))
        reach = dist(start, recovery_point) / 7.2 + 0.18
        if motion_end - arrival >= reach:
            react = max(arrival, motion_end - reach - 0.15)
            actors.append(
                _actor(
                    recoverer,
                    "recoverer",
                    [_anchor(react, start), _anchor(motion_end, recovery_point)],
                    [(0.0, "stance_1"), (react, "RUN"), (motion_end, "recover")],
                    "offense" if from_offense else "defense",
                )
            )

    ball_start = BallEnd(point=(tee[0], 0.25, tee[1]))
    catch = (
        BallEnd(actor=receiver.key, hold="hands")
        if receiver
        else BallEnd(point=(land[0], 0.15, land[1]))
    )
    balls = [
        MotionBall(start=0, end=kick_at, style="rest", origin=ball_start),
        MotionBall(start=kick_at, end=arrival, style="kick", origin=ball_start, target=catch),
        MotionBall(
            start=arrival,
            end=bounce_end if roll else end_return if loose and receiver else duration,
            style="bounce" if roll else "held" if receiver else "rest",
            origin=catch,
            target=BallEnd(point=(min(109.6, land[0] + 2.6), 0.15, _lane(land[1] + 0.25)))
            if roll
            else None,
        ),
    ]
    if roll:
        bounce_point = balls[-1].target
        assert bounce_point is not None
        stop = BallEnd(point=(min(110.0, land[0] + 4.6), 0.15, _lane(land[1] + 0.45)))
        balls.extend(
            (
                MotionBall(
                    start=bounce_end, end=motion_end, style="roll", origin=bounce_point, target=stop
                ),
                MotionBall(start=motion_end, end=duration, style="rest", origin=stop),
            )
        )
    events = [Milestone(kind="kick", t=kick_at), Milestone(kind="arrival", t=arrival)]
    if receiver:
        events.append(Milestone(kind="possession", t=arrival))
    if draw_contact:
        events.append(Milestone(kind="contact", t=contact_time))
    note = None
    if loose and receiver:
        drawn_recovery = recoverer and any(a.key == recoverer.key for a in actors)
        on_ground = BallEnd(point=(recovery_point[0], 0.14, recovery_point[1]))
        end = (
            BallEnd(actor=recoverer.key, hold="hands")
            if drawn_recovery and recoverer
            else on_ground
        )
        balls.extend(
            (
                MotionBall(
                    start=end_return, end=motion_end, style="bounce", origin=catch, target=end
                ),
                MotionBall(
                    start=motion_end,
                    end=duration,
                    style="held" if drawn_recovery else "rest",
                    origin=end,
                ),
            )
        )
        events.append(Milestone(kind="loose", t=end_return))
        if drawn_recovery:
            events.append(Milestone(kind="recovery", t=motion_end))
        else:
            note = "The kick and return are shown. The recovery remains in the play description."
    if facts.touchdown or facts.out_of_bounds:
        events.append(Milestone(kind="score" if facts.touchdown else "out_of_bounds", t=end_return))
    return _output(
        actions,
        facts,
        fitted,
        actors,
        balls,
        events,
        motion_end,
        origin=kick_at,
        live_end=live_end,
        note=note,
    )
