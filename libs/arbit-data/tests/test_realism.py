"""The owner's review of the play-type clips against the game's video (OWN-037)."""

import math

import pytest
from arbit_data.live.choreography import BULLET, CYCLES, SNAP, choreograph
from live_cases import POSITIONS, SCRIPTED, facts, script, units


def full(name):
    """The play as the review renders draw it: positions and each team's units."""
    return script(name, positions=POSITIONS, with_units=True)


def actor(made, key):
    return next(a for a in made.actors if a.key == key)


def at(segments, t):
    return next((s for s in segments if s.start <= t < s.end), segments[-1])


@pytest.mark.parametrize(
    "name",
    [n for n in SCRIPTED if facts(n).template not in (None, "punt", "kickoff", "field_goal")],
)
def test_the_teams_center_snaps_the_ball_and_stays_over_it(name):
    made = full(name)
    if not any(a.key in ("passer", "quarterback", "rusher") for a in made.actors):
        return
    play = facts(name)
    center = units(name)[play.offense]["center"]
    snapper = actor(made, "snapper")
    assert snapper.espn_id == center[0] and snapper.side == "offense"
    los = made.lines[0].x
    assert [s.pose for s in snapper.segments[:2]] == ["snap_ready", "snap_release"]
    assert all(abs(s.x0 - los) <= 0.5 and abs(s.x1 - los) <= 0.5 for s in snapper.segments)


def test_a_run_shows_the_quarterback_handing_off_right_after_the_snap():
    made = full("run_gap")
    qb = actor(made, "quarterback")
    assert qb.espn_id == units("run_gap")[facts("run_gap").offense]["quarterback"][0]
    held = [s for s in made.ball if s.state == "held"]
    assert [s.actor for s in held[:2]] == ["quarterback", "rusher"]
    assert held[0].end <= SNAP + 0.9
    assert "handoff_give" in {s.pose for s in qb.segments}
    back = actor(made, "rusher")
    taking = at(back.segments, held[0].end)
    assert taking.pose == "take"


def test_the_sacked_quarterback_escapes_right_before_the_hit():
    made = full("sack")
    qb = actor(made, "passer")
    hit = next(s for s in qb.segments if s.pose == "hit_back")
    escape = [
        s
        for s in qb.segments
        if s.pose == "RUN" and s.end > hit.start - 0.5 and s.start < hit.start
    ]
    assert escape
    assert escape[-1].z1 > escape[0].z0  # his right is the far side


def test_the_intended_receiver_is_drawn_and_the_interceptor_beats_him_to_the_ball():
    made = full("interception_intended_receiver")
    receiver, picker = actor(made, "receiver"), actor(made, "interceptor")
    to_picker = next(
        s for s in made.ball if s.state == "flight" and s.target.actor == "interceptor"
    )
    near = at(receiver.segments, to_picker.end - 1e-3)
    caught = at(picker.segments, to_picker.end - 1e-3)
    assert math.hypot(near.x1 - caught.x1, near.z1 - caught.z1) < 4.0  # both there with the ball
    assert caught.pose.startswith("catch_high")
    waiting = [
        s
        for s in picker.segments
        if to_picker.end - 1.0 < s.end <= to_picker.end - 0.37 and s.pose.startswith("stance")
    ]
    assert sum(s.end - s.start for s in waiting) < 0.6  # he doesn't stand there waiting for it


def test_a_pass_tipped_at_the_line_pops_up_to_the_interceptor():
    """Clip 03: the owner confirmed from the video that the pass was tipped and caught."""
    made = full("interception_return")
    tipper = actor(made, "tipper")
    assert tipper.label == "A.Booker" or tipper.espn_id
    flights = [s for s in made.ball if s.state == "flight" and s.start > SNAP + 0.5]
    assert flights[0].target.point is not None and flights[1].target.actor == "interceptor"
    assert flights[1].spin == "tumble"
    assert "arms_jump" in {s.pose for s in tipper.segments}


def test_the_teams_long_snapper_snaps_a_punt():
    made = full("home_punt_downed")
    snapper = actor(made, "snapper")
    assert (
        snapper.espn_id
        == units("home_punt_downed")[facts("home_punt_downed").offense]["long_snapper"][0]
    )


def test_a_cover_man_keeps_his_cushion_and_backpedals_without_the_ball():
    made = full("pass_deep_tackled_by_safety")
    love = next(a for a in made.actors if a.role == "tackler")
    poses = [s.pose for s in love.segments]
    assert "BACKPEDAL" in poses and "drop_b" not in poses and "drop_c" not in poses
    receiver = actor(made, "receiver")
    catch = next(s for s in made.ball if s.state == "flight" and s.target.actor == "receiver")
    rx = at(receiver.segments, catch.end - 1e-3).x1
    assert at(love.segments, catch.end - 1e-3).x1 >= rx  # still over the top at the catch


@pytest.mark.parametrize("name", [n for n in SCRIPTED if facts(n).template == "pass"])
def test_with_units_the_ball_and_receiver_still_arrive_together(name):
    made = full(name)
    for flight in (
        s for s in made.ball if s.state == "flight" and s.target and s.target.actor == "receiver"
    ):
        receiver = actor(made, "receiver")
        catching = at(receiver.segments, flight.end - 1e-3)
        assert catching.pose.startswith("catch") and catching.end == pytest.approx(flight.end)
        waiting = [
            s
            for s in receiver.segments
            if flight.end - 0.6 < s.end <= flight.end
            and s.pose not in CYCLES
            and not s.pose.startswith("catch")
        ]
        assert not waiting
    assert BULLET == 32.0


def test_only_the_quarterback_uses_his_ball_holding_frames():
    for name in SCRIPTED:
        for a in full(name).actors:
            if a.key in ("passer", "quarterback") or (
                a.key == "rusher"
                and facts(name).run
                and facts(name).run.style in ("scramble", "sneak", "kneel")
            ):
                continue
            assert not {"drop_a", "drop_b", "drop_c", "ready"} & {s.pose for s in a.segments}, (
                name,
                a.key,
            )


def test_pass_interference_is_contact_while_the_ball_is_in_the_air_and_the_flag_comes_then():
    """The owner's rules: after the release, before the ball arrives, more than a yard past the
    line, on a catchable ball; through the back, an arm bar or cutting off his path."""
    made = full("penalty_wipes_out_pass")
    los = made.lines[0].x
    flight = next(s for s in made.ball if s.state == "flight" and s.start > SNAP + 0.5)
    defender, receiver = actor(made, "defender"), actor(made, "receiver")
    contact = next(s for s in defender.segments if s.pose in ("lunge", "wrap", "drive"))
    assert flight.start < contact.start < flight.end
    assert contact.x0 > los + 1.0
    assert any(s.pose == "stumble" for s in receiver.segments if s.start >= contact.start - 0.05)
    # Catchable: the same play without the foul has him catching it right there.
    clean = choreograph(
        facts("penalty_wipes_out_pass").before,
        "penalty_wipes_out_pass:test",
        None,
        POSITIONS,
        units("penalty_wipes_out_pass"),
    )
    pass_flight = next(s for s in clean.ball if s.state == "flight" and s.start > SNAP + 0.5)
    would = at(actor(clean, "receiver").segments, pass_flight.end - 0.12 - 1e-3)
    landing = flight.target.point
    assert math.hypot(landing[0] - would.x1, landing[2] - would.z1) < 2.5
    (flag,) = made.props
    assert contact.start <= flag.start <= contact.start + 0.6


def test_offensive_pass_interference_is_the_receiver_pushing_off_and_he_still_catches_it():
    made = full("offensive_pass_interference")
    flight = next(
        s for s in made.ball if s.state == "flight" and s.target and s.target.actor == "receiver"
    )
    pushed = [
        a
        for a in made.actors
        if a.side == "defense"
        and any(s.pose == "stumble" and flight.start < s.start < flight.end for s in a.segments)
    ]
    assert pushed
    assert any(s.state == "held" and s.actor == "receiver" for s in made.ball)
    (flag,) = made.props
    assert flight.start < flag.start < flight.end + 0.6


def test_a_holding_flag_on_a_sack_lands_by_the_defender_who_held():
    made = full("defensive_holding_wipes_out_sack")
    play = facts("defensive_holding_wipes_out_sack")
    held_by = next(iter(p.espn_id for p in play.players if p.role == "penalized"), None)
    if held_by is None:
        pytest.skip("ESPN names no penalized player on this play")
    marked = next(a for a in made.actors if a.espn_id == held_by)
    (flag,) = made.props
    x, z = at(marked.segments, flag.start).x1, at(marked.segments, flag.start).z1
    assert math.hypot(flag.at[0] - x, flag.at[2] - z) < 2.0


@pytest.mark.parametrize("name", [n for n in SCRIPTED if full(n).props])
def test_an_official_throws_each_flag_from_where_he_stands(name):
    """The owner allowed drawing officials who throw the flags (OWN-037)."""
    made = full(name)
    officials = [a for a in made.actors if a.role == "official"]
    assert len(officials) >= len(made.props)
    for flag in made.props:
        thrower = min(
            officials,
            key=lambda a: math.hypot(
                at(a.segments, flag.start).x1 - flag.origin[0],
                at(a.segments, flag.start).z1 - flag.origin[2],
            ),
        )
        hand = at(thrower.segments, flag.start)
        assert math.hypot(hand.x1 - flag.origin[0], hand.z1 - flag.origin[2]) < 0.5
        assert hand.pose in ("off_reach", "off_throw")
        for seg in thrower.segments:
            if seg.pose == "OFF_RUN":
                assert seg.start >= SNAP  # he doesn't move before the snap
                speed = math.hypot(seg.x1 - seg.x0, seg.z1 - seg.z0) / (seg.end - seg.start)
                assert 4.0 <= speed <= 7.0  # a jog
