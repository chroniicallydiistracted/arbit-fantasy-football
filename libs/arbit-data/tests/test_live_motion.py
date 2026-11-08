"""The replacement run plan uses only stored PBP and point-in-time team context."""

from arbit_data.live.actions import sequence
from arbit_data.live.play_facts import interpret
from test_live_actions import TEAMS, converted, stat


def run(yards=65):
    text = f"(Shotgun) R.Firth right tackle for {yards} yards, TOUCHDOWN."
    play = converted("RUSH", text, [stat("nfl-back", "R.Firth", 11, "nfl-home", yards)])
    return play.model_copy(
        update={"stat_yardage": str(yards), "whistle_at": "2026-10-01T00:00:10.600Z"}
    )


def setup(play):
    from arbit_data.live.motion import MotionContext

    facts = interpret(play, TEAMS)
    context = MotionContext(
        facts=facts,
        names={"100": "Q.Able", "103": "R.Firth", "104": "C.Gray"},
        positions={"103": ("RB",), "104": ("C",)},
        units={"1": {"quarterback": ("100", "Q.Able"), "center": ("104", "C.Gray")}},
    )
    return sequence(play, facts), context


def test_shotgun_run_fits_exchange_and_center_release_to_the_play():
    from arbit_data.live.motion import plan

    actions, context = setup(run())
    made = plan(actions, context)
    assert made is not None and made.version == 2
    assert made.whistle == 11.2
    assert [ball.style for ball in made.ball] == ["rest", "snap", "held", "exchange", "held"]
    handoff = next(s for s in made.milestones if s.kind == "exchange")
    assert handoff.t - 0.6 > 0.9
    carrier = next(a for a in made.actors if a.espn_id == "103")
    center = next(a for a in made.actors if a.espn_id == "104")
    score = next(s for s in made.milestones if s.kind == "score")
    crossing = next(k for k in carrier.track if k.t == score.t)
    assert crossing.x == 100 and crossing.vx > 3
    assert carrier.track[-1].x > 101 and carrier.track[-1].vx == 0
    assert max(k.z for k in carrier.track) - carrier.track[0].z > 5
    assert center.track[-1].x > center.track[0].x
    assert made.timing.overrun == 0


def test_new_clock_text_does_not_reseed_actor_paths():
    from arbit_data.live.motion import plan

    play = run()
    original = plan(*setup(play))
    corrected = plan(*setup(play.model_copy(update={"clock": "8:59"})))
    assert original is not None and corrected is not None
    assert original.actors == corrected.actors and original.ball == corrected.ball


def test_short_observed_duration_keeps_the_provider_clock_and_reports_overrun():
    from arbit_data.live.motion import plan

    play = run().model_copy(update={"whistle_at": "2026-10-01T00:00:02Z"})
    made = plan(*setup(play))
    assert made is not None
    assert made.whistle == 2.6
    assert made.motion_end > made.whistle
    assert made.timing.overrun > 0


def test_run_without_timing_has_a_generated_whistle_only():
    from arbit_data.live.motion import plan

    play = run().model_copy(update={"whistle_at": None})
    made = plan(*setup(play))
    assert made is not None
    assert made.timing.provider_seconds is None
    assert made.whistle >= next(event.t for event in made.milestones if event.kind == "score")


def test_animation_builder_negotiates_run_preview_and_keeps_legacy_default(monkeypatch):
    from arbit_data.live import animation
    from arbit_data.live.contracts import FieldPoint

    play = run().model_copy(update={"end": FieldPoint(yard_line=100, team_id="1")})
    _, context = setup(play)
    monkeypatch.setattr(animation, "current_plays", lambda *_: [play])
    monkeypatch.setattr(
        animation,
        "_game",
        lambda *_: {
            "home": "1",
            "away": "2",
            "home_code": "SEA",
            "away_code": "CHI",
            "kickoff": None,
            "names": {"1": ["Seattle"], "2": ["Chicago"]},
        },
    )
    monkeypatch.setattr(
        animation,
        "_shared",
        lambda *_: (
            context.names,
            context.positions,
            {"SEA": context.units["1"]},
        ),
    )
    old = animation.build(None, play.event_id)
    new = animation.build(None, play.event_id, script_version=2)
    assert old is not None and new is not None
    old_run = old["entries"][0]
    new_run = new["entries"][0]
    assert old_run["script"].version == 1
    assert new_run["script"].version == 2
    assert old_run["board"] == new_run["board"]


def test_pass_plan_keeps_release_arrival_and_possession_separate():
    from arbit_data.live.motion import plan

    play = converted(
        "PASS",
        "(Shotgun) Q.Able pass short right to B.Baker to SEA 44 for 9 yards (D.Dunn).",
        [
            stat("nfl-qb", "Q.Able", 15, "nfl-home", 9),
            stat("nfl-qb", "Q.Able", 111, "nfl-home", 3),
            stat("nfl-target", "B.Baker", 21, "nfl-home", 9),
            stat("nfl-target", "B.Baker", 113, "nfl-home", 6),
            stat("nfl-target", "B.Baker", 115, "nfl-home"),
            stat("nfl-picker", "D.Dunn", 79, "nfl-away"),
        ],
    )
    made = plan(*setup(play))
    assert made is not None
    timing = {event.kind: event.t for event in made.milestones}
    assert timing["release"] < timing["arrival"] < timing["possession"] <= timing["dead"]
    flight = next(ball for ball in made.ball if ball.style == "pass")
    assert flight.target is not None and flight.target.actor == "espn:101"
    receiver = next(a for a in made.actors if a.espn_id == "101")
    assert receiver.track[-1].x == 44


def test_interception_plan_only_adds_pursuit_for_the_credited_target():
    from arbit_data.live.motion import plan
    from test_live_actions import interception

    for tackle, expected in [(("nfl-target", "B.Baker"), True), (("nfl-back", "R.Firth"), False)]:
        play = interception(tackle)
        made = plan(*setup(play))
        assert made is not None
        (target,) = [a for a in made.actors if a.espn_id == "101"]
        assert any(cue.pose == "wrap" for cue in target.poses) is expected
        caught = next(ball for ball in made.ball if ball.style == "pass")
        assert caught.target is not None and caught.target.actor == "espn:102"


def test_corrected_kick_replays_the_return_loose_ball_and_recovery():
    from arbit_data.live.motion import plan

    original = (
        "Q.Able kicks 60 yards from SEA 35 to CHI 5. D.Dunn to CHI 30 for 25 yards (B.Baker)."
    )
    play = converted(
        "KICK_OFF",
        original
        + " Seattle challenged the ruling, and the play was REVERSED. "
        + original
        + " FUMBLES (B.Baker), RECOVERED by SEA-B.Baker at CHI 31.",
        [
            stat("nfl-qb", "Q.Able", 41, "nfl-home", 60),
            stat("nfl-picker", "D.Dunn", 45, "nfl-away", 25),
            stat("nfl-picker", "D.Dunn", 52, "nfl-away"),
            stat("nfl-target", "B.Baker", 91, "nfl-home"),
            stat("nfl-target", "B.Baker", 59, "nfl-home", 0),
        ],
    ).model_copy(update={"whistle_at": "2026-10-01T00:00:09.500Z"})
    made = plan(*setup(play))
    assert made is not None
    assert [ball.style for ball in made.ball] == ["rest", "kick", "held", "bounce", "held"]
    assert [ball.origin.actor for ball in made.ball if ball.style == "held"] == [
        "espn:102",
        "espn:101",
    ]
    time = {event.kind: event.t for event in made.milestones}
    assert time["kick"] < time["possession"] < time["loose"] < time["recovery"]
    assert len([a for a in made.actors if a.espn_id == "101"]) == 1


def test_direct_run_keeps_the_snap_and_first_hold_at_the_same_anchor():
    from arbit_data.live.motion import plan

    actions, context = setup(run())
    context = type(context)(
        facts=context.facts,
        names=context.names,
        positions={**context.positions, "103": ("QB",)},
        units=context.units,
    )
    script = plan(actions, context)
    assert script is not None
    snap = next(cue for cue in script.ball if cue.style == "snap")
    held = next(cue for cue in script.ball if cue.style == "held")
    assert snap.end == held.start
    assert snap.target == held.origin


def test_receiver_leaves_at_snap_and_moves_through_a_catch():
    from math import dist, hypot

    from arbit_data.live.choreography import SNAP
    from arbit_data.live.motion import plan
    from arbit_data.live.trajectory import sample

    play = converted(
        "PASS",
        "(Shotgun) Q.Able pass short right to B.Baker to SEA 44 for 9 yards (D.Dunn).",
        [
            stat("nfl-qb", "Q.Able", 15, "nfl-home", 9),
            stat("nfl-qb", "Q.Able", 111, "nfl-home", 3),
            stat("nfl-target", "B.Baker", 21, "nfl-home", 9),
            stat("nfl-target", "B.Baker", 113, "nfl-home", 6),
            stat("nfl-target", "B.Baker", 115, "nfl-home"),
            stat("nfl-picker", "D.Dunn", 79, "nfl-away"),
        ],
    )
    made = plan(*setup(play))
    assert made is not None
    receiver = next(a for a in made.actors if a.espn_id == "101")
    early = sample(receiver.track, SNAP + 0.55)
    assert dist((early.x, early.z), (receiver.track[0].x, receiver.track[0].z)) > 0.65
    arrival = next(event.t for event in made.milestones if event.kind == "arrival")
    catch = sample(receiver.track, arrival)
    assert hypot(catch.vx, catch.vz) > 1.0


def test_touchback_with_no_catch_continues_after_landing():
    from arbit_data.live.motion import plan

    play = converted(
        "KICK_OFF",
        "Q.Able kicks 65 yards from SEA 35 to end zone, Touchback.",
        [stat("nfl-qb", "Q.Able", 41, "nfl-home", 65)],
    )
    made = plan(*setup(play))
    assert made is not None
    assert [cue.style for cue in made.ball] == ["rest", "kick", "bounce", "roll", "rest"]
    for a, b in zip(made.ball[1:-1], made.ball[2:], strict=True):
        assert a.end == b.start
        assert a.target == b.origin


def test_shared_tackle_approaches_a_moving_carrier_and_finishes_at_the_official_spot():
    from math import dist, hypot

    from arbit_data.live.motion import plan
    from arbit_data.live.trajectory import sample

    play = converted(
        "RUSH",
        "(Shotgun) R.Firth right tackle to SEA 44 for 9 yards (D.Dunn; F.Ford).",
        [
            stat("nfl-back", "R.Firth", 11, "nfl-home", 9),
            stat("nfl-picker", "D.Dunn", 79, "nfl-away"),
            stat("nfl-assist", "F.Ford", 82, "nfl-away"),
        ],
    ).model_copy(update={"stat_yardage": "9"})
    actions, context = setup(play)
    made = plan(actions, context)
    assert made is not None
    contact = next(m.t for m in made.milestones if m.kind == "contact")
    carrier = next(a for a in made.actors if a.role == "rusher")
    at_hit = sample(carrier.track, contact)
    assert hypot(at_hit.vx, at_hit.vz) > 1
    assert carrier.track[-1].x == 44 and at_hit.x < 44
    defenders = [a for a in made.actors if a.role == "tackler"]
    assert len(defenders) == 2
    for defender in defenders:
        meeting = sample(defender.track, next(c.start for c in defender.poses if c.pose == "wrap"))
        assert dist((at_hit.x, at_hit.z), (meeting.x, meeting.z)) < 2
