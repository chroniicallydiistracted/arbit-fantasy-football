"""Play facts from real ESPN plays (tests/fixtures/live/play-facts.examples.json)."""

import json
from pathlib import Path

import pytest
from arbit_data.live.normalize import normalize_play
from arbit_data.live.play_facts import GameTeams, PlayFacts, interpret, text_codes

FIXTURE = Path(__file__).parents[3] / "tests/fixtures/live/play-facts.examples.json"
CASES = {case["name"]: case for case in json.loads(FIXTURE.read_text())["cases"]}


def read(name: str):
    case = CASES[name]
    play = normalize_play(case["play"], case["event_id"], 2026)
    teams = GameTeams.build(
        case["home"], case["away"], case["home_code"], case["away_code"], case["text_codes"]
    )
    return play, interpret(play, teams), teams


def ready(facts: PlayFacts) -> bool:
    return facts.template is not None and not facts.missing


@pytest.mark.parametrize("name", sorted(CASES))
def test_every_play_reads_and_spots_stay_on_the_field(name):
    _, facts, _ = read(name)
    for spot in (facts.start, facts.end, facts.action_end):
        assert spot is None or 0 <= spot <= 100
    if facts.kick and facts.kick.landing is not None:
        assert 0 <= facts.kick.landing <= 110


def test_completion_places_the_catch_from_yards_after_catch():
    play, facts, _ = read("pass_catch_spot_and_missed_pat")
    assert ready(facts) and facts.touchdown and facts.end == 100
    assert facts.start + facts.yards == facts.end
    catch = facts.passing
    assert catch.result == "complete" and (catch.depth, catch.side) == ("deep", "left")
    assert catch.yards_after_catch == play.yards_after_catch
    assert catch.air_yards + catch.yards_after_catch == facts.yards
    assert catch.catch_spot == facts.start + catch.air_yards
    assert facts.point_after.kind == "extra_point" and facts.point_after.good is False
    assert facts.point_after.miss == "wide_left"


def test_completion_without_yards_after_catch_keeps_depth_and_still_animates():
    play, facts, _ = read("pass_without_yards_after_catch")
    assert play.yards_after_catch is None and ready(facts)
    assert facts.passing.catch_spot is None
    assert (facts.passing.depth, facts.passing.side) == ("short", "right")
    assert facts.out_of_bounds and facts.shotgun


def test_incompletion_keeps_depth_side_and_the_bracketed_qb_hit():
    _, facts, _ = read("pass_incomplete_qb_hit")
    assert ready(facts) and facts.passing.result == "incomplete"
    assert (facts.passing.depth, facts.passing.side) == ("short", "right")
    assert facts.passing.qb_hit_by == ("T.Hopper",)
    assert facts.end == facts.start


def test_interception_spot_comes_from_the_text_and_the_return_from_espn():
    _, facts, _ = read("interception_return")
    assert ready(facts) and facts.turnover
    pick = facts.passing
    assert pick.result == "intercepted" and pick.catch_spot == pick.air_yards + facts.start
    assert "returner" in {p.role for p in facts.players}
    assert facts.end < pick.catch_spot  # returned back toward the passer's goal line


def test_sack_and_runs_end_where_start_plus_yards_says():
    for name, shape in (
        ("sack", "sack"),
        ("run_gap", "run"),
        ("scramble", "scramble"),
        ("kneel", "kneel"),
    ):
        _, facts, _ = read(name)
        assert facts.shape == shape and ready(facts)
        assert facts.start + facts.yards == facts.end == facts.action_end
    assert {p.role for p in read("sack")[1].players} >= {"passer", "sackedBy"}
    run = read("run_gap")[1].run
    assert (run.style, run.side, run.gap) == ("run", "right", "tackle")
    assert read("scramble")[1].run.style == "scramble"


def test_home_team_punt_uses_yard_line_because_yards_to_endzone_is_wrong():
    play, facts, _ = read("home_punt_downed")
    # ESPN repeats yardLine in yardsToEndzone for this home-team punt instead of flipping it (ENG-033).
    assert play.start.yards_to_endzone == play.start.yard_line
    assert ready(facts) and facts.spot_source == "yard_line"
    assert facts.start + facts.kick.distance == facts.kick.landing == facts.end
    assert facts.kick.result == "downed"


def test_punt_results():
    _, returned, _ = read("away_punt_returned")
    assert returned.kick.result == "returned" and returned.kick.return_yards == 3
    assert returned.start + returned.kick.distance == returned.kick.landing
    assert read("punt_fair_catch")[1].kick.result == "fair_catch"
    touchback = read("punt_touchback_with_penalty")[1]
    assert touchback.kick.result == "touchback" and touchback.kick.landing == 100
    assert ready(touchback) and touchback.penalties[0].status == "accepted"


def test_kickoff_results():
    _, returned, _ = read("kickoff_returned")
    assert ready(returned) and returned.kick.result == "returned"
    assert returned.start + returned.kick.distance == returned.kick.landing
    touchback = read("kickoff_touchback")[1]
    assert touchback.kick.result == "touchback" and touchback.kick.landing == 100
    assert read("kickoff_short_of_landing_zone")[1].kick.result == "short_of_landing_zone"
    assert read("kickoff_onside")[1].kick.onside


def test_out_of_bounds_kickoff_finds_the_kicker_espn_lists_only_as_penalized():
    play, facts, _ = read("kickoff_out_of_bounds")
    assert "kicker" not in {p.role for p in play.participants}
    flagged = next(p.espn_id for p in play.participants if p.role == "penalized")
    assert ready(facts) and facts.kick.result == "out_of_bounds"
    assert any(p.role == "kicker" and p.espn_id == flagged for p in facts.players)


def test_field_goal_distance_counts_the_end_zone_and_the_hold():
    for name, result, miss in (
        ("field_goal_good", "good", None),
        ("field_goal_wide_right", "no_good", "wide_right"),
        ("field_goal_blocked", "blocked", None),
    ):
        _, facts, _ = read(name)
        assert ready(facts) and (facts.kick.result, facts.kick.miss) == (result, miss)
        # 10 yards of end zone plus the hold, 8 yards back on 50 of 57 captured kicks.
        assert 17 <= facts.kick.distance - (100 - facts.start) <= 19


def test_rams_home_spot_matches_the_text_not_yards_to_endzone():
    play, facts, _ = read("rams_home_spot")
    assert play.end.yards_to_endzone == play.end.yard_line  # unflipped for the home team
    assert facts.end == facts.action_end == 100 - 14  # "to LAC 14"
    assert facts.start + facts.yards == facts.end


def test_text_codes_pair_with_teams_even_when_espn_uses_gamebook_codes():
    _, facts, teams = read("kickoff_short_of_landing_zone")
    assert teams.codes["LA"] == teams.home and teams.codes["LAC"] == teams.away
    assert facts.offense == teams.home and facts.start == 35
    paired = GameTeams.build("1", "2", "AAA", "BBB", {"AAA", "ZZZ"})
    assert paired.codes["ZZZ"] == "2"
    assert text_codes(["T.Loop kicks 62 yards from BLT 35 to BUF 3"]) == {"BLT", "BUF"}
    assert text_codes(["R.Johnson for 50 yards"]) == set()


def test_replay_reversal_reads_the_restated_play():
    _, facts, _ = read("replay_reversed")
    assert facts.review == "reversed" and "Replay Official" not in facts.text
    assert ready(facts) and facts.start + facts.yards == facts.end


def test_penalties():
    _, flagged, teams = read("no_play_penalty")
    assert flagged.shape == "penalty" and flagged.template is None and flagged.reason == "no_play"
    [penalty] = flagged.penalties
    assert penalty.type == "Encroachment" and penalty.no_play and penalty.yards == 3
    assert penalty.team in (teams.home, teams.away)
    _, declined, _ = read("declined_penalty")
    assert ready(declined) and declined.penalties[0].status == "declined"
    assert declined.penalties[0].yards is None


def test_plays_without_a_template_yet_say_why():
    _, fumble, teams = read("fumble_lost")
    assert fumble.template is None and fumble.reason == "fumble"
    assert (
        fumble.fumble.forced and fumble.fumble.lost and fumble.fumble.recovered_by == fumble.defense
    )
    assert read("lateral")[1].reason == "lateral"
    timeout = read("timeout")[1]
    assert timeout.shape == "timeout" and timeout.reason == "not_a_play" and timeout.start is None


def test_two_point_try_attached_to_the_touchdown():
    _, facts, _ = read("two_point_success")
    assert facts.touchdown and facts.point_after.kind == "two_point" and facts.point_after.good


def test_new_fields_stay_out_of_the_payload_when_espn_omits_them():
    raw = dict(CASES["run_gap"]["play"])
    for key in ("yardsAfterCatch", "penalty", "review"):
        raw.pop(key, None)
    raw["start"] = {k: v for k, v in raw["start"].items() if k != "yardLine"}
    payload = normalize_play(raw, CASES["run_gap"]["event_id"], 2026).model_dump(mode="json")
    assert not {"yards_after_catch", "penalty", "review"} & payload.keys()
    assert "yard_line" not in payload["start"] and "yard_line" in payload["end"]
    # ESPN sends a penalty object only for accepted penalties (193 of 193 captured; 0 of 28 declined).
    kept = normalize_play(
        CASES["no_play_penalty"]["play"], CASES["no_play_penalty"]["event_id"], 2026
    )
    assert (
        kept.penalty is not None and kept.penalty.status == "accepted" and kept.penalty.yards == 3
    )
