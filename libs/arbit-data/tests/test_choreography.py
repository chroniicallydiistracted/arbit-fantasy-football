"""Play scripts from real ESPN plays: rules every generated play must keep."""

import json
import math
import re
from pathlib import Path

import pytest
from arbit_data.live.choreography import (
    CYCLES,
    LONGEST_STILL,
    MOMENTUM,
    SLOWEST_RUN,
    STILL,
    TOP_SPEED,
    PlayScript,
    choreograph,
)
from arbit_data.live.normalize import normalize_play
from arbit_data.live.play_facts import GameTeams, interpret

ROOT = Path(__file__).parents[3]
CASES = {
    case["name"]: case
    for case in json.loads((ROOT / "tests/fixtures/live/play-facts.examples.json").read_text())[
        "cases"
    ]
}
FRAMES = {
    match.group(1)
    for path in (ROOT / "assets/sprites/frames").glob("*.txt")
    for match in re.finditer(r"^== (\S+)", path.read_text(), re.M)
}
SCRIPTED = (
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


def facts(name: str):
    case = CASES[name]
    play = normalize_play(case["play"], case["event_id"], 2026)
    teams = GameTeams.build(
        case["home"], case["away"], case["home_code"], case["away_code"], case["text_codes"]
    )
    return interpret(play, teams)


def script(name: str, seed: str = "test", names: dict[str, str] | None = None) -> PlayScript | None:
    return choreograph(facts(name), f"{name}:{seed}", names)


def at(segments, t: float):
    return next((s for s in segments if s.start <= t < s.end), segments[-1])


def test_scripts_only_for_the_slice_two_templates():
    for name in CASES:
        made = script(name)
        assert (made is not None) == (name in SCRIPTED), name


@pytest.mark.parametrize("name", SCRIPTED)
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
    ids = [a.espn_id for a in made.actors]
    assert len(ids) == len(set(ids))
    assert set(ids) <= {p.espn_id for p in play.players}


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
            resting = seg.pose.startswith(("ground", "rise", "kneel", "point", "arms", "spike"))
            if held and not resting and seg.start > 0:
                assert seg.end - seg.start <= LONGEST_STILL + 1e-6, (
                    actor.key,
                    seg.pose,
                    seg.end - seg.start,
                )


def test_a_short_receiver_settles_facing_the_quarterback_and_comes_back_to_the_ball():
    made = script("pass_without_yards_after_catch")
    receiver = next(a for a in made.actors if a.key == "receiver")
    flight = next(s for s in made.ball if s.state == "flight" and s.target.actor == "receiver")
    waiting = [
        s
        for s in receiver.segments
        if s.end <= flight.end - 0.27 and s.start >= receiver.segments[1].end
    ]
    assert waiting and all(s.facing == "left" for s in waiting)  # set, facing the passer
    assert {s.pose for s in waiting} >= {"ready"} and any(
        s.z0 != s.z1 for s in waiting
    )  # a side step
    catching = at(receiver.segments, flight.end - 1e-3)
    assert catching.x1 < catching.x0  # back toward the ball


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
