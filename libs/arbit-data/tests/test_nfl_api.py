"""The NFL API's game record as stored plays (OWN-041), checked against ESPN's record of the same
game: CHI at SEA, 2026-11-02. ESPN's plays are in board-plays.example.json."""

import json
import re
from pathlib import Path

import pytest
from arbit_data.live.board import GameBoard
from arbit_data.live.nfl_api import GameLink, clock_end, to_live_plays
from arbit_data.live.normalize import normalize_play
from arbit_data.live.play_facts import GameTeams, interpret, text_codes

FIXTURES = Path(__file__).parents[3] / "tests/fixtures/live"
NFL = json.loads((FIXTURES / "nfl-api-chi-at-sea.example.json").read_text())
ESPN_GAME = next(
    g
    for g in json.loads((FIXTURES / "board-plays.example.json").read_text())["games"]
    if g["event_id"] == "401873036"
)
LINK = GameLink(
    NFL["game"]["id"], NFL["event_id"], NFL["home"], NFL["away"], NFL["home_code"], NFL["away_code"]
)


def seconds(clock: str | None) -> int:
    minutes, secs = (clock or "0:00").split(":")
    return int(minutes) * 60 + int(secs)


@pytest.fixture(scope="module")
def converted():
    return {p.provider_id: p for p in to_live_plays(NFL["game"], LINK, NFL["ids"], 2026)}


@pytest.fixture(scope="module")
def espn():
    return {raw["id"]: normalize_play(raw, "401873036", 2026) for raw in ESPN_GAME["plays"]}


@pytest.fixture(scope="module")
def teams(espn):
    return GameTeams.build("26", "3", "SEA", "CHI", seen=text_codes(p.text for p in espn.values()))


def test_every_football_play_has_espns_play_id(converted, espn):
    """ESPN's play ID is its event ID followed by the NFL play ID."""
    football = [p for p in converted.values() if p.kind != "administrative" and p.text]
    assert len(football) >= 150
    assert all(p.provider_id in espn for p in football)


def test_tries_are_folded_into_their_touchdowns(converted):
    kinds = {p.nfl["play"]["playType"] for p in converted.values()}
    assert not kinds & {"XP_KICK", "PAT2"}
    touchdowns = [
        p for p in converted.values() if p.nfl["play"].get("scoringPlayType") == "TOUCHDOWN"
    ]
    assert touchdowns and all(p.point_after is not None and "try" in p.nfl for p in touchdowns)
    assert all(re.search(r"extra point is|TWO-POINT CONVERSION", p.text) for p in touchdowns)


def test_the_score_after_each_play_is_espns(converted, espn):
    for play_id, play in converted.items():
        if play_id in espn and espn[play_id].kind != "administrative":
            assert (play.away_score, play.home_score) == (
                espn[play_id].away_score,
                espn[play_id].home_score,
            ), play.text


def test_the_snap_state_is_espns(converted, espn):
    """Possession, down, distance and the spot at the snap, as ESPN recorded them."""
    for play_id, play in converted.items():
        theirs = espn.get(play_id)
        if theirs is None or theirs.kind in ("administrative", "unknown"):
            continue
        ours, start = play.start, theirs.start
        assert (ours.team_id, ours.down, ours.distance, ours.yard_line) == (
            start.team_id,
            start.down,
            start.distance,
            start.yard_line,
        ), play.text


def test_the_clock_at_the_whistle_matches_espns_scoring_plays(converted, espn):
    """ESPN times a scoring play's clock after the play; the NFL's snap clock less the play's
    time is that clock, within the second the clock shows."""
    checked = 0
    for play_id, play in converted.items():
        theirs = espn.get(play_id)
        timed = (
            play.snap_at is not None and play.whistle_at is not None
        )  # Swift's 5:41 score has no whistle time
        if (
            theirs is not None
            and theirs.scoring_play
            and timed
            and play.nfl["play"]["playType"] in ("PASS", "RUSH", "FIELD_GOAL")
        ):
            # Whole seconds: a whistle half a second into a second can show either one.
            assert abs(seconds(play.clock_end) - seconds(theirs.clock)) <= 1, play.text
            assert play.clock != theirs.clock  # the NFL's clock is the snap's
            checked += 1
    assert checked >= 7


def test_kickoffs_and_tries_have_no_clock_at_the_whistle(converted):
    kickoffs = [p for p in converted.values() if p.nfl["play"]["playType"] == "KICK_OFF"]
    assert kickoffs and all(p.clock_end is None for p in kickoffs)
    assert (
        clock_end(
            {
                "playType": "XP_KICK",
                "clockTime": "5:25",
                "playStartTime": "2026-11-03T01:00:00Z",
                "playEndTime": "2026-11-03T01:00:04Z",
            }
        )
        is None
    )


def test_roles_from_stats(converted, teams):
    """A pass names its passer and receiver, a run its rusher, a tackle its tackler; an
    interception's intended receiver is "other", as ESPN names him."""
    for play in converted.values():
        facts = interpret(play, teams)
        roles = {p.role for p in play.participants}
        if facts.shape == "pass" and facts.passing and facts.passing.result == "complete":
            assert {"passer", "receiver"} <= roles, play.text
        if facts.shape == "run" and "No Play" not in play.text:
            assert "rusher" in roles, play.text
        if facts.shape == "interception":
            assert {"passer", "passDefender", "returner"} <= roles and "receiver" not in roles


def test_jersey_numbers_are_the_games_own(converted):
    """Quenton Nelson wore 53 that night; nflverse's roster said 56 and NFL's season roster none."""
    (false_start,) = [
        p for p in converted.values() if "PENALTY on SEA-Q.Nelson, False Start" in p.text
    ]
    (penalized,) = [p.espn_id for p in false_start.participants if p.role == "penalized"]
    assert false_start.jerseys[penalized] == "53"


def test_the_board_from_the_nfl_record(converted, teams):
    """The board shows the snap clock on a scoring play, runs to the whistle's, and numbers a
    foul from the game's own record, declined fouls too."""
    board = GameBoard(teams, "SEA", "CHI", {"26": ["Seattle"], "3": ["Chicago"]})
    found = {}
    for play in sorted(converted.values(), key=lambda p: float(p.sequence or 0)):
        made = board.boards(play, interpret(play, teams))
        found[play.provider_id] = made
    touchdown = next(
        m[0]
        for p, m in found.items()
        if "C.Williams pass short right to L.Burden for 1 yard, TOUCHDOWN" in converted[p].text
    )
    assert (touchdown.before.clock, touchdown.after.clock) == ("5:30", "5:25")
    numbers = {
        r.jersey for made in found.values() for b in made for r in b.results if r.kind == "penalty"
    }
    assert {"53", "29", "6"} <= numbers  # Nelson's false start; Jobe's and Gordon's declined fouls


def test_a_deleted_play_is_cancelled():
    game = json.loads(json.dumps(NFL["game"]))
    target = next(p for p in game["driveChart"]["plays"] if p["playType"] == "RUSH")
    target["playDeleted"] = True
    plays = {p.provider_id: p for p in to_live_plays(game, LINK, NFL["ids"], 2026)}
    assert plays[f"401873036{target['playId']}"].cancelled
