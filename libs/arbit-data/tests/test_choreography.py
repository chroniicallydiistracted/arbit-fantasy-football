"""Play scripts from real ESPN plays: rules every generated play must keep."""

import json
import math

import pytest
from arbit_data.live.choreography import (
    CYCLES,
    DEEPEST,
    LONGEST_STILL,
    MOMENTUM,
    SLOWEST_RUN,
    SNAP,
    STILL,
    TOP_SPEED,
    PlayScript,
    choreograph,
)
from arbit_data.live.normalize import normalize_play
from arbit_data.live.play_facts import GameTeams, interpret
from live_cases import CASES, FRAMES, ROOT, SCRIPTED, at, facts, script

# The plays slice 2 draws from the snap to the whistle: they end on ESPN's spot.
SCRIMMAGE = (
    "pass_catch_spot_and_missed_pat",
    "pass_without_yards_after_catch",
    "pass_incomplete_qb_hit",
    "interception_return",
    "sack",
    "run_gap",
    "scramble",
    "kneel",
    "rams_home_spot",
    "replay_reversed",
    "declined_penalty",
    "two_point_success",
)
# Poses a player may hold still after the snap: down, kneeling, holding for a kick, on a recovered
# ball, celebrating.
RESTING = ("ground", "rise", "kneel", "point", "arms", "spike", "hold_", "recover", "snap_", "off_")


def test_every_play_but_a_lateral_and_a_timeout_has_a_script():
    for name in CASES:
        made = script(name)
        assert (made is not None) == (name in SCRIPTED), name


@pytest.mark.parametrize("name", SCRIMMAGE)
def test_the_play_ends_on_espns_spot(name):
    play, made = facts(name), script(name)
    held = [s for s in made.ball if s.state == "held"]
    if play.passing and play.passing.result == "incomplete":
        assert made.ball[-1].state == "rest"  # the ball ends on the turf, the spot unchanged
        return
    carrier = next(a for a in made.actors if a.key == held[-1].actor)
    final = carrier.segments[-1].x1
    if play.touchdown:
        assert final >= 100 if carrier.side == "offense" else final <= 0
    else:
        assert final == pytest.approx(play.action_end, abs=0.05)


@pytest.mark.parametrize("name", SCRIPTED)
def test_only_named_players_appear_and_each_once(name):
    play, made = facts(name), script(name)
    ids = [a.espn_id for a in made.actors if a.espn_id is not None]
    assert len(ids) == len(set(ids))
    assert set(ids) <= {p.espn_id for p in play.players}
    keys = [a.key for a in made.actors]
    assert len(keys) == len(set(keys))
    # A player ESPN gives no ID, such as a long snapper, is drawn only under the text's name.
    assert all(a.label for a in made.actors if a.espn_id is None and a.role != "official")


@pytest.mark.parametrize("name", SCRIPTED)
def test_nobody_slides_and_nobody_outruns_a_sprinter(name):
    for actor in script(name).actors:
        for seg in actor.segments:
            seconds = seg.end - seg.start
            speed = math.hypot(seg.x1 - seg.x0, seg.z1 - seg.z0) / seconds if seconds else 0.0
            limit = TOP_SPEED * 1.08 if seg.pose in CYCLES else MOMENTUM.get(seg.pose, STILL)
            assert speed <= limit + 1e-6, (actor.key, seg.pose, round(speed, 2))
            # `_e` is the renderer's empty-handed copy of a frame drawn with the ball.
            assert seg.pose in CYCLES or seg.pose.removesuffix("_e") in FRAMES, seg.pose
        for before, after in zip(actor.segments, actor.segments[1:], strict=False):
            assert after.start == pytest.approx(before.end) and after.x0 == pytest.approx(before.x1)


@pytest.mark.parametrize("name", SCRIPTED)
def test_everyone_moves_naturally(name):
    """Owner review 2026-11-03: no slow-motion running to make the timing work, no speeding up
    after a catch, and no one frozen while waiting."""
    for actor in script(name).actors:
        runs = [
            math.hypot(s.x1 - s.x0, s.z1 - s.z0) / (s.end - s.start)
            for s in actor.segments
            if s.pose == "RUN" and s.end - s.start > 0.25
        ]
        if runs:
            assert min(runs) >= SLOWEST_RUN, (actor.key, round(min(runs), 2))
            assert max(runs) - min(runs) <= 0.15, (actor.key, "changed pace")
        for seg in actor.segments:
            held = seg.pose not in CYCLES and seg.pose not in MOMENTUM
            if held and not seg.pose.startswith(RESTING) and seg.start > 0:
                assert seg.end - seg.start <= LONGEST_STILL + 1e-6, (
                    actor.key,
                    seg.pose,
                    seg.end - seg.start,
                )


@pytest.mark.parametrize("name", SCRIMMAGE)
def test_the_receiver_and_the_ball_arrive_together(name):
    """Owner review of the clips (OWN-037): the throw's timing decides it, the receiver is never
    slowed or left waiting, a deep pass keeps its pace and a short one is at most a bullet."""
    made = script(name)
    to_receiver = [
        s
        for s in made.ball
        if s.state == "flight" and s.target is not None and s.target.actor == "receiver"
    ]
    for flight in to_receiver:
        receiver = next(a for a in made.actors if a.key == "receiver")
        catching = at(receiver.segments, flight.end - 1e-3)
        assert catching.pose.startswith(("catch_reach", "catch_high"))
        assert catching.end == pytest.approx(flight.end)
        waiting = [
            s
            for s in receiver.segments
            if flight.end - 0.6 < s.end <= flight.end
            and s.pose not in CYCLES
            and not s.pose.startswith("catch")
        ]
        assert not waiting, [s.pose for s in waiting]
        passer = next(a for a in made.actors if a.key == "passer")
        thrown = at(passer.segments, flight.start)
        caught = at(receiver.segments, flight.end - 1e-3)
        speed = math.hypot(caught.x1 - thrown.x0, caught.z1 - thrown.z0) / (
            flight.end - flight.start - 0.25
        )
        assert speed <= 32.0 + 1.5, speed  # a bullet at most; hands are a yard off the feet


def test_names_come_from_the_roster_and_the_text_only_when_unambiguous():
    play = facts("run_gap")
    tacklers = [p.espn_id for p in play.players if p.role in ("tackler", "assistedBy")]
    assert len(tacklers) == 2
    unnamed = script("run_gap")
    assert all(
        a.label is None for a in unnamed.actors if a.espn_id in tacklers
    )  # two names, order unknown
    named = script("run_gap", names={tacklers[0]: "T.Okada", tacklers[1]: "E.Jones"})
    labels = {a.espn_id: a.label for a in named.actors}
    assert labels[tacklers[0]] == "T.Okada" and labels[tacklers[1]] == "E.Jones"
    rusher = next(a for a in unnamed.actors if a.role == "rusher")
    assert rusher.label == "R.Johnson"  # one rusher, one name: the text is enough


@pytest.mark.parametrize("name", SCRIPTED)
def test_everyone_starts_on_his_side_of_the_line(name):
    """Owner review 2026-11-04 (OWN-035): at the snap the offense is on or behind the line of
    scrimmage and the defense on or beyond it, no deeper than a safety. A kick returner waits
    where the kick comes down, and kickoff coverage lines up at the receiving 40 (2026 rule)."""
    made = script(name)
    los = made.lines[0].x
    for actor in made.actors:
        x0 = actor.segments[0].x0
        if made.template == "kickoff" and actor.side == "offense":
            assert x0 <= los + 25 + 1e-6, (actor.key, x0)
        elif actor.side == "offense":
            assert x0 <= los + 1e-6, (actor.key, x0 - los)
        elif actor.role != "returner":
            assert los - 1e-6 <= x0 <= los + DEEPEST + 1e-6, (actor.key, x0 - los)
        if made.template != "penalty" or actor.role != "penalized":
            moving = [s for s in actor.segments if s.pose in CYCLES and s.start < SNAP - 1e-6]
            assert not moving, (actor.key, "moves before the snap")


@pytest.mark.parametrize("name", SCRIPTED)
def test_the_ball_is_always_somewhere(name):
    made = script(name)
    ball = sorted(made.ball, key=lambda s: s.start)
    assert ball[0].start == 0 and ball[-1].end == pytest.approx(made.duration)
    for before, after in zip(ball, ball[1:], strict=False):
        assert after.start == pytest.approx(before.end), (before.state, after.state)
    keys = {a.key for a in made.actors}
    for seg in ball:
        if seg.state == "held":
            assert seg.actor in keys
        if seg.state == "flight":
            for end in (seg.origin, seg.target):
                assert (end.actor in keys) != (end.point is not None)


def test_the_ball_meets_the_receiver_in_a_catching_pose():
    for name in (
        "pass_catch_spot_and_missed_pat",
        "pass_without_yards_after_catch",
        "rams_home_spot",
    ):
        made = script(name)
        flight = next(s for s in made.ball if s.state == "flight" and s.target.actor == "receiver")
        receiver = next(a for a in made.actors if a.key == "receiver")
        catching = at(receiver.segments, flight.end - 1e-3)
        assert catching.pose.startswith(
            ("catch_reach", "catch_high")
        ) and catching.end == pytest.approx(flight.end)
        assert (
            next(s for s in made.ball if s.start == pytest.approx(flight.end)).actor == "receiver"
        )


def test_the_catch_is_where_espn_says_the_ball_was_caught():
    play, made = facts("pass_catch_spot_and_missed_pat"), script("pass_catch_spot_and_missed_pat")
    flight = next(s for s in made.ball if s.state == "flight" and s.target.actor == "receiver")
    receiver = next(a for a in made.actors if a.key == "receiver")
    assert at(receiver.segments, flight.end - 1e-3).x1 == pytest.approx(play.passing.catch_spot)


def test_a_tackler_already_on_the_field_is_not_drawn_twice():
    made = script("interception_return")
    keys = [a.key for a in made.actors]
    assert keys.count("passer") == 1 and "interceptor" in keys
    chaser = next(a for a in made.actors if a.role == "tackler")
    assert chaser.side == "offense" and chaser.label == "A.Lucas"  # the only tackler named


def test_same_play_same_script_and_another_revision_may_differ():
    assert script("run_gap") == script("run_gap")
    assert script("run_gap", "first") != script("run_gap", "corrected")


def test_the_published_schema_matches_the_contract():
    published = json.loads(
        (ROOT / "packages/contracts/schemas/play-script.schema.json").read_text()
    )
    assert published == PlayScript.model_json_schema()


def test_an_eligibility_report_is_not_the_play():
    case = CASES["pass_incomplete_qb_hit"]
    raw = {**case["play"], "text": "L.Newman reported in as eligible.  " + case["play"]["text"]}
    play = normalize_play(raw, case["event_id"], 2026)
    teams = GameTeams.build(
        case["home"], case["away"], case["home_code"], case["away_code"], case["text_codes"]
    )
    made = choreograph(interpret(play, teams), "eligible")
    assert "reported in" not in made.caption and "pass incomplete" in made.caption
    passer = next(a for a in made.actors if a.key == "passer")
    assert passer.label != "L.Newman"
