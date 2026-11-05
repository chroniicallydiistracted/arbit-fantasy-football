"""The stadium board's state at each play (slice 5), on whole real games.

Each game in the fixture is every play ESPN posted, in order, so a board's score and timeouts
come from the plays before it exactly as they would live.
"""

import json
import re
from pathlib import Path

import pytest
from arbit_data.live.board import GameBoard, PlayBoard
from arbit_data.live.normalize import normalize_play
from arbit_data.live.play_facts import GameTeams, interpret, text_codes

FIXTURE = Path(__file__).parents[3] / "tests/fixtures/live/board-plays.example.json"
GAMES = {game["event_id"]: game for game in json.loads(FIXTURE.read_text())["games"]}
SEA, CHI = "26", "3"  # CHI at SEA, 2026-11-02
DAL, ARI = "6", "22"  # ARI at DAL, with overtime
JAX, IND = "30", "11"  # IND at JAX


def run(event: str, edit=None, names=None) -> list[tuple[str, tuple[PlayBoard, ...]]]:
    """Every play's text and boards, in order. `edit` may change a raw play first, and `names`
    replaces the names the text may call each team by."""
    game = GAMES[event]
    raws = [edit(raw) if edit else raw for raw in game["plays"]]
    plays = [normalize_play(raw, game["event_id"], 2026) for raw in raws]
    teams = GameTeams.build(
        game["home"],
        game["away"],
        game["home_code"],
        game["away_code"],
        seen=text_codes(p.text for p in plays),
    )
    roster = {
        team: [tuple(player) for player in players] for team, players in game["roster"].items()
    }
    board = GameBoard(teams, game["home_code"], game["away_code"], names or game["names"], roster)
    return [(play.text, board.boards(play, interpret(play, teams))) for play in plays]


def find(boards, start: str, after: str | None = None) -> tuple[PlayBoard, ...]:
    """The boards of the first play whose text starts with `start`, after one starting `after`."""
    seen = after is None
    for text, made in boards:
        if seen and text.startswith(start):
            return made
        seen = seen or text.startswith(after or "")
    raise AssertionError(f"no play starts with {start!r}")


def score(state) -> tuple[int | None, int | None]:
    return state.away.score, state.home.score


def timeouts(state) -> tuple[int | None, int | None]:
    return state.away.timeouts, state.home.timeouts


def spot(state) -> str | None:
    if state.spot is None:
        return None
    if state.spot.team_id is None:
        return str(state.spot.yard)
    return f"{state.home.code if state.spot.team_id == state.home.team_id else state.away.code} {state.spot.yard}"


@pytest.fixture(scope="module")
def chi_at_sea():
    return run("401873036")


def test_the_opening_kickoff(chi_at_sea):
    (made,) = find(chi_at_sea, "C.Santos kicks 56 yards from CHI 35 to SEA 9")
    before, after = made.before, made.after
    assert (before.period, before.clock) == (1, "15:00")
    assert (before.away.code, before.home.code) == ("CHI", "SEA")
    assert score(before) == (0, 0) and timeouts(before) == (3, 3)
    assert before.situation == "kickoff" and before.possession == CHI and spot(before) == "CHI 35"
    # The return ends at the SEA 32: Seattle's ball, first and ten.
    assert after.possession == SEA and after.situation == "down"
    assert (after.down, after.distance, spot(after)) == (1, 10, "SEA 32")
    assert made.results == ()


def test_down_distance_and_spot_come_from_the_snap_and_the_end(chi_at_sea):
    (made,) = find(chi_at_sea, "Z.Charbonnet left guard to SEA 37 for 5 yards")
    assert (made.before.down, made.before.distance, spot(made.before)) == (1, 10, "SEA 32")
    assert (made.after.down, made.after.distance, spot(made.after)) == (2, 5, "SEA 37")
    assert not made.before.goal_to_go


def test_a_punt_gives_the_other_team_the_ball(chi_at_sea):
    (made,) = find(chi_at_sea, "M.Dickson punts 63 yards to end zone")
    assert made.before.possession == SEA and (made.before.down, made.before.distance) == (4, 5)
    assert made.after.possession == CHI and (
        made.after.down,
        made.after.distance,
        spot(made.after),
    ) == (1, 10, "CHI 20")


def test_a_touchdown_shows_six_then_the_try_shows_espns_score(chi_at_sea):
    touchdown, tried = find(
        chi_at_sea, "(No Huddle, Shotgun) C.Williams pass short right to L.Burden for 1 yard"
    )
    assert touchdown.before.goal_to_go and (touchdown.before.down, touchdown.before.distance) == (
        2,
        1,
    )
    assert score(touchdown.before) == (0, 0)
    assert score(touchdown.after) == (6, 0)
    assert [(r.kind, r.text, r.team_id) for r in touchdown.results] == [
        ("touchdown", "TOUCHDOWN", CHI)
    ]
    assert touchdown.after.situation == "extra_point" and touchdown.after.possession == CHI
    assert tried.part == "try" and tried.before == touchdown.after
    assert score(tried.after) == (7, 0)
    assert [(r.text, r.team_id) for r in tried.results] == [("EXTRA POINT GOOD", CHI)]


def test_a_missed_try_keeps_the_six(chi_at_sea):
    touchdown, tried = find(
        chi_at_sea, "(Shotgun) S.Darnold pass deep left to J.Smith-Njigba for 43 yards, TOUCHDOWN"
    )
    assert score(touchdown.after)[1] == score(touchdown.before)[1] + 6
    assert score(tried.after) == score(touchdown.after) == (13, 9)  # ESPN's score after the play
    assert [r.text for r in tried.results] == ["NO GOOD"]


def test_a_two_point_try(chi_at_sea):
    (_touchdown, tried), *others = [
        made for _text, made in chi_at_sea if made[-1].before.situation == "two_point"
    ]
    assert not others
    assert score(tried.after)[1] - score(tried.before)[1] == 2
    assert [r.text for r in tried.results] == ["TWO-POINT GOOD"]


def test_field_goals(chi_at_sea):
    (good,) = find(chi_at_sea, "C.Santos 44 yard field goal is GOOD")
    assert score(good.after)[0] - score(good.before)[0] == 3
    assert [(r.text, r.team_id) for r in good.results] == [("FIELD GOAL GOOD", CHI)]
    (blocked,) = find(chi_at_sea, "J.Myers 33 yard field goal is BLOCKED")
    assert score(blocked.after) == score(blocked.before)
    assert [(r.text, r.team_id) for r in blocked.results] == [("BLOCKED", CHI)]


def test_turnovers(chi_at_sea):
    (picked,) = find(
        chi_at_sea, "(Shotgun) S.Darnold pass short middle intended for A.Barner INTERCEPTED"
    )
    assert [(r.text, r.team_id) for r in picked.results] == [("INTERCEPTED", CHI)]
    assert picked.after.possession == CHI
    (fumbled,) = find(chi_at_sea, "(Shotgun) C.Williams pass short right to C.Loveland to CHI 21")
    assert [(r.text, r.team_id) for r in fumbled.results] == [("FUMBLE", SEA)]
    downs = [
        made for _text, made in chi_at_sea if made[0].results and made[0].results[0].kind == "downs"
    ]
    assert len(downs) == 1
    (made,) = downs[0]
    assert made.before.down == 4 and made.after.possession != made.before.possession


def test_only_scores_turnovers_misses_and_flags_show_a_result(chi_at_sea):
    """Every card has its reason in the play's own text, and every other play has none."""
    reasons = {
        "touchdown": "TOUCHDOWN",
        "field_goal": "field goal is GOOD",
        "blocked": "BLOCKED",
        "no_good": "No Good",
        "interception": "INTERCEPTED",
        "fumble": "FUMBLES",
        "extra_point": "extra point is GOOD",
        "two_point": "ATTEMPT SUCCEEDS",
        "penalty": "PENALTY",
    }
    carded = 0
    for text, made in chi_at_sea:
        for board in made:
            for result in board.results:
                carded += 1
                if result.kind == "downs":
                    assert board.before.down == 4
                else:
                    assert reasons[result.kind].casefold() in text.casefold(), (result.kind, text)
        if (
            not any(board.results for board in made) and "No Play" not in text
        ):  # a flag wiped it out
            assert not any(
                word.casefold() in text.casefold()
                for word in ("TOUCHDOWN", "INTERCEPTED", "field goal is GOOD")
            )
    assert carded >= 15


def test_called_timeouts_count_down_and_reset_at_halftime(chi_at_sea):
    (called,) = find(chi_at_sea, "Timeout #1 by SEA")
    assert (
        called.after.home.timeouts == 2
        and called.after.away.timeouts == called.before.away.timeouts
    )
    # Every play after it in the half shows two left, and the second half starts with three.
    states = [made[0] for text, made in chi_at_sea if made[0].before.period in (3, 4)]
    assert timeouts(states[0].before) == (3, 3)


def test_a_lost_challenge_costs_the_challenger_a_timeout():
    boards = run("401873024")
    (challenged,) = find(boards, "(Shotgun) D.Prescott scrambles right end to DAL 32 for 1 yard")
    assert timeouts(challenged.before) == (3, 3)
    assert timeouts(challenged.after) == (3, 2)  # Dallas, the home team, challenged and lost


def test_overtime_starts_with_two_timeouts_each():
    boards = run("401873024")
    first = next(made[0] for _text, made in boards if made[0].before.period == 5)
    assert timeouts(first.before) == (2, 2)


def test_an_interception_returned_for_a_touchdown_shows_both_cards():
    boards = run("401873028")
    made = next(made for text, made in boards if "INTERCEPTED" in text and "TOUCHDOWN" in text)
    play = made[0]
    assert [r.kind for r in play.results] == ["interception", "touchdown"]
    defense = play.results[0].team_id
    assert play.results[1].team_id == defense
    side = "home" if defense == play.before.home.team_id else "away"
    assert getattr(play.after, side).score == getattr(play.before, side).score + 6


@pytest.mark.parametrize("event", sorted(GAMES))
def test_the_last_board_shows_espns_final_score(event):
    boards = run(event)
    final = GAMES[event]["final"]
    last = boards[-1][1][-1].after
    assert (last.away.score, last.home.score) == (final["away"], final["home"])


@pytest.mark.parametrize("event", sorted(GAMES))
def test_scores_never_go_down_and_timeouts_stay_in_range(event):
    previous = (0, 0)
    for _text, made in run(event):
        for board in made:
            for state in (board.before, board.after):
                now = score(state)
                assert now[0] >= previous[0] and now[1] >= previous[1]
                previous = now
                for left in timeouts(state):
                    assert left is not None and 0 <= left <= 3


def test_a_challenge_by_a_team_it_cant_name_leaves_timeouts_unknown_for_the_half():
    def edit(raw):
        text = raw.get("text", "")
        return {**raw, "text": text.replace("Dallas challenged", "The coach challenged")}

    boards = run("401873024", edit)
    (challenged,) = find(boards, "(Shotgun) D.Prescott scrambles right end to DAL 32 for 1 yard")
    assert timeouts(challenged.after) == (None, None)
    later = [made[0] for _text, made in boards if made[0].before.period == 2]
    assert all(timeouts(board.before) == (None, None) for board in later)
    third = next(made[0] for _text, made in boards if made[0].before.period == 3)
    assert timeouts(third.before) == (3, 3)


def test_a_play_without_a_score_keeps_the_last_known_one_unless_it_scored(chi_at_sea):
    def edit(raw):
        if raw.get("text", "").startswith(
            ("Z.Charbonnet left guard to SEA 37", "C.Santos 44 yard field goal")
        ):
            return {k: v for k, v in raw.items() if k not in ("homeScore", "awayScore")}
        return raw

    boards = run("401873036", edit)
    (plain,) = find(boards, "Z.Charbonnet left guard to SEA 37")
    assert score(plain.after) == (0, 0)
    (kick,) = find(boards, "C.Santos 44 yard field goal is GOOD")
    assert score(kick.after) == (None, None)
    # The next play with a score brings it back.
    assert score(boards[-1][1][-1].after) == (34, 17)


def test_the_published_schema_matches_the_contract():
    root = Path(__file__).parents[3]
    published = json.loads((root / "packages/contracts/schemas/play-board.schema.json").read_text())
    assert published == PlayBoard.model_json_schema()


def test_a_flag_on_the_try_doesnt_take_the_extra_point_back():
    """BUF against BAL, Q4 5:58: ESPN put the extra point on the touchdown play (36), then
    recorded a delay of game on the try with the score before the kick (35). A play that scores
    nothing never lowers the board's score. The same pattern, after CHI's first touchdown."""
    game = GAMES["401873036"]
    plays = list(game["plays"])
    at = next(
        i
        for i, raw in enumerate(plays)
        if raw.get("text", "").startswith(
            "(No Huddle, Shotgun) C.Williams pass short right to L.Burden"
        )
    )
    flag = next(
        raw for raw in plays if raw.get("text", "").startswith("PENALTY on CHI, Delay of Game")
    )
    early = {
        **flag,
        "id": "401873036999999",
        "homeScore": 0,
        "awayScore": 6,
        "sequenceNumber": "54250",
    }
    GAMES["edited"] = {
        **game,
        "event_id": "401873036",
        "plays": [*plays[: at + 1], early, *plays[at + 1 :]],
    }
    try:
        boards = run("edited")
    finally:
        del GAMES["edited"]
    touchdown, tried = boards[at][1]
    (penalty,) = boards[at + 1][1]
    assert score(tried.after) == (7, 0)
    assert score(penalty.before) == score(penalty.after) == (7, 0)


def test_a_name_both_teams_share_doesnt_charge_either():
    """Both Los Angeles teams have the location "Los Angeles"; ESPN's text then uses the full
    name. A challenge by a name both teams share can't be charged to one of them."""
    shared = {DAL: ["Dallas", "Dallas Cowboys"], ARI: ["Dallas", "Arizona Cardinals"]}
    boards = run("401873024", names=shared)
    (challenged,) = find(boards, "(Shotgun) D.Prescott scrambles right end to DAL 32 for 1 yard")
    assert timeouts(challenged.after) == (None, None)


GOOD = {"touchdown", "field_goal", "extra_point", "two_point", "safety"}
BAD = {"no_good", "blocked", "interception", "fumble", "downs"}


@pytest.mark.parametrize("event", sorted(GAMES))
def test_scores_are_good_turnovers_and_misses_bad_and_flags_yellow(event):
    """The owner's colors (OWN-039): scores green, turnovers and misses red, penalties yellow."""
    for _text, made in run(event):
        for board in made:
            for result in board.results:
                expected = (
                    "good" if result.kind in GOOD else "bad" if result.kind in BAD else "flag"
                )
                assert result.tone == expected, result


def test_a_penalty_shows_the_foul_the_team_and_the_number(chi_at_sea):
    (false_start,) = find(chi_at_sea, "(Shotgun) PENALTY on CHI-J.Jackson, False Start")
    (card,) = false_start.results
    assert (card.kind, card.text, card.team_id, card.tone) == (
        "penalty",
        "FALSE START",
        CHI,
        "flag",
    )
    # Jonah Jackson has no ESPN ID in nflverse's roster, so he is found by name on his team.
    (jackson,) = [p for p in GAMES["401873036"]["roster"][CHI] if p[1].startswith("Jonah Jackson")]
    assert jackson[0] is None and card.jersey == jackson[2]


@pytest.mark.parametrize("event", sorted(GAMES))
def test_every_foul_ESPN_names_a_player_for_gets_his_number(event):
    """The number is that player's: on the flagged team's roster, by ESPN ID or by the name the
    text gives ("Ja.Williams" is Jaylon, not Jordan)."""
    game = GAMES[event]
    for text, made in run(event):
        for card in (r for board in made for r in board.results if r.kind == "penalty"):
            assert card.text == card.text.upper() and card.team_id in (game["home"], game["away"])
            named = re.search(r"PENALTY on [A-Z]{2,3}-([A-Z][a-z]*\.[A-Za-z' .-]+?),", text, re.I)
            if named is None:
                assert card.jersey is None  # a team foul
                continue
            prefix, last = named.group(1).split(".", 1)
            players = [
                p
                for p in game["roster"][card.team_id]
                if p[1].split(" ", 1)[0].startswith(prefix)
                and re.sub(r",? (Jr\.|Sr\.|II|III|IV|V)$", "", p[1]).endswith(" " + last)
            ]
            assert card.jersey == (players[0][2] if len(players) == 1 else None), (text, players)


def test_a_team_foul_has_no_number(chi_at_sea):
    (delay,) = find(chi_at_sea, "PENALTY on CHI, Delay of Game")
    (card,) = delay.results
    assert (card.text, card.team_id, card.jersey) == ("DELAY OF GAME", CHI, None)


def test_a_declined_penalty_says_so(chi_at_sea):
    declined = [
        r
        for _t, made in chi_at_sea
        for b in made
        for r in b.results
        if r.kind == "penalty" and r.detail
    ]
    assert declined and all(r.detail in ("DECLINED", "OFFSETTING") for r in declined)


def test_the_flag_comes_after_the_plays_own_result(chi_at_sea):
    for _text, made in chi_at_sea:
        for board in made:
            kinds = [r.kind for r in board.results]
            if "penalty" in kinds:
                first = kinds.index("penalty")
                assert all(kind == "penalty" for kind in kinds[first:])


def test_the_clock_runs_to_the_end_of_the_play_when_its_known():
    """An end-of-play clock, as the owner's NFL feed will give, is the board's clock after it."""
    game = GAMES["401873036"]
    plays = [normalize_play(raw, game["event_id"], 2026) for raw in game["plays"]]
    teams = GameTeams.build(
        game["home"],
        game["away"],
        game["home_code"],
        game["away_code"],
        seen=text_codes(p.text for p in plays),
    )
    board = GameBoard(teams, game["home_code"], game["away_code"], game["names"])
    for play in plays:
        if play.text.startswith("Z.Charbonnet left guard to SEA 37"):
            (made,) = board.boards(play, interpret(play, teams), clock_end="14:16")
            assert (made.before.clock, made.after.clock) == ("14:55", "14:16")
            return
        board.boards(play, interpret(play, teams))
    raise AssertionError("play not found")


def test_numbers_come_from_the_flagged_teams_roster_only(chi_at_sea):
    """A foul's player is looked up on his own team: CHI's J.Jackson is never SEA's."""
    seen = 0
    for _text, made in chi_at_sea:
        for card in (
            r for board in made for r in board.results if r.kind == "penalty" and r.jersey
        ):
            seen += 1
            assert card.jersey in {p[2] for p in GAMES["401873036"]["roster"][card.team_id]}
    assert seen >= 10
