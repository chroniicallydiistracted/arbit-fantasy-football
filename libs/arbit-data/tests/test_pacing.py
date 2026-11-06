"""Plays paced to the NFL's real snap-to-whistle time (OWN-041), on CHI at SEA's NFL record."""

import json
import math
from pathlib import Path

import pytest
from arbit_data.live.animation import real_seconds
from arbit_data.live.choreography import LONGEST_STILL, SLOWEST_RUN, SNAP, choreograph
from arbit_data.live.nfl_api import GameLink, to_live_plays
from arbit_data.live.pacing import pace
from arbit_data.live.play_facts import GameTeams, interpret, text_codes

NFL = json.loads(
    (Path(__file__).parents[3] / "tests/fixtures/live/nfl-api-chi-at-sea.example.json").read_text()
)
LINK = GameLink(
    NFL["game"]["id"], NFL["event_id"], NFL["home"], NFL["away"], NFL["home_code"], NFL["away_code"]
)
PLAYS = to_live_plays(NFL["game"], LINK, NFL["ids"], 2026)
TEAMS = GameTeams.build("26", "3", "SEA", "CHI", seen=text_codes(p.text for p in PLAYS))


def scripts():
    for play in PLAYS:
        facts = interpret(play, TEAMS)
        if facts.shape in ("timeout", "other"):
            continue
        script = choreograph(facts, f"{play.provider_id}:pacing")
        if script is not None and real_seconds(play):
            yield play, script, pace(script, real_seconds(play))


def speed(seg) -> float:
    seconds = seg.end - seg.start
    return math.hypot(seg.x1 - seg.x0, seg.z1 - seg.z0) / seconds if seconds > 0 else 0.0


def test_the_whistle_comes_at_the_real_time_when_the_real_play_was_longer():
    paced = 0
    for play, script, made in scripts():
        real = real_seconds(play)
        if real > script.whistle - SNAP:
            assert made.whistle == pytest.approx(SNAP + real, abs=1e-3)
            paced += 1
        else:
            assert made == script  # a play the NFL timed faster keeps Arbit's timing
    assert paced >= 100


def test_nothing_looks_like_slow_motion():
    """Runs stay at running pace and still poses never freeze: the action slows only so far, and
    the rest of the real time is the end of the play."""
    for _play, script, made in scripts():
        for actor in made.actors:
            for seg in actor.segments:
                if seg.pose == "RUN" and seg.end > SNAP and seg.end - seg.start > 0.25:
                    assert speed(seg) >= SLOWEST_RUN, (made.caption, actor.key)
                if seg.pose.startswith("idle_") and seg.start > script.whistle:
                    assert seg.end - seg.start <= LONGEST_STILL + 1e-6


def test_the_quarterback_throws_later():
    """The owner: "a QB takes longer to throw"."""
    later = 0
    for _play, script, made in scripts():
        flights = [
            s
            for s in script.ball
            if s.state == "flight" and s.origin and s.origin.actor == "passer"
        ]
        paced = [
            s for s in made.ball if s.state == "flight" and s.origin and s.origin.actor == "passer"
        ]
        if flights and paced and made.whistle > script.whistle:
            assert paced[0].start >= flights[0].start
            later += paced[0].start > flights[0].start + 0.05
    assert later >= 10


def test_every_timeline_is_whole_to_the_end():
    for _play, _script, made in scripts():
        for actor in made.actors:
            assert actor.segments[0].start == 0
            assert actor.segments[-1].end == pytest.approx(made.duration)
            for before, after in zip(actor.segments, actor.segments[1:], strict=False):
                assert after.start == pytest.approx(before.end, abs=1e-5)
                assert (after.x0, after.z0) == pytest.approx((before.x1, before.z1), abs=1e-5)


def test_a_play_without_real_times_is_unchanged():
    play = next(p for p in PLAYS if p.kind == "rush")
    script = choreograph(interpret(play, TEAMS), "unchanged")
    assert pace(script, None) == script
