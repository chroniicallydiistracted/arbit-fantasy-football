"""Players line up by their depth chart positions and make their position's first move (OWN-036)."""

import math

import pytest
from arbit_data.live import alignment as A
from arbit_data.live.choreography import _ROLE_SLOTS, SNAP
from live_cases import POSITIONS, SCRIPTED, facts, script

# Where each kind of position starts, in yards past the line of scrimmage.
BOXES = {
    "OL": (-1.0, -0.4),
    "TE": (-1.0, -0.3),
    "WR": (-8.0, 0.0),
    "RB": (-8.0, -3.0),
    "FB": (-8.0, -3.0),
    "QB": (-6.0, -0.4),
    "DL": (0.9, 1.1),
    "EDGE": (0.9, 1.1),
    "LB": (3.0, 6.0),
    "CB": (4.0, 8.0),
    "NB": (4.0, 7.0),
    "S": (6.0, 15.0),
}
KICKS = ("punt", "kickoff", "field_goal", "extra_point")
CONTEXT = A.Context(los=40.0, ball_z=26.0, shotgun=True, kind="pass")


def placed(name):
    return script(name, positions=POSITIONS)


def test_the_offensive_line_is_left_to_right_across_the_ball_on_the_offenses_side():
    spots = {code: A.spot(code, CONTEXT) for code in ("LT", "LG", "C", "RG", "RT")}
    across = [spots[code][1] for code in ("LT", "LG", "C", "RG", "RT")]
    assert across == sorted(across)  # the offense's left is the near sideline
    assert all(x < CONTEXT.los for x, _ in spots.values())


def test_the_defense_lines_up_across_from_the_offense_with_its_left_on_the_far_side():
    ldE, rde = A.spot("LDE", CONTEXT), A.spot("RDE", CONTEXT)
    assert ldE[1] > CONTEXT.ball_z > rde[1]  # the left end faces the right tackle
    assert ldE[0] == rde[0] == CONTEXT.los + 1
    assert A.spot("LCB", CONTEXT)[1] > CONTEXT.ball_z > A.spot("RCB", CONTEXT)[1]
    assert A.spot("FS", CONTEXT)[0] > A.spot("SS", CONTEXT)[0] > A.spot("MLB", CONTEXT)[0]


def test_a_3_4_outside_linebacker_rushes_off_the_edge_and_a_4_3_one_stands_off_the_ball():
    rows = [
        {
            "dt": "2026-10-31",
            "team": "SEA",
            "espn_id": "1",
            "pos_grp": "Base 3-4 D",
            "pos_abb": "WLB",
            "pos_rank": 1,
        },
        {
            "dt": "2026-10-31",
            "team": "DAL",
            "espn_id": "2",
            "pos_grp": "Base 4-3 D",
            "pos_abb": "WLB",
            "pos_rank": 1,
        },
    ]
    positions = A.from_depth_charts(rows)
    assert positions == {"1": ("WOLB",), "2": ("WLB",)}
    assert A.spot("WOLB", CONTEXT)[0] == CONTEXT.los + 1  # on the line
    assert A.spot("WLB", CONTEXT)[0] > CONTEXT.los + 3  # off the ball
    assert A.spot("WOLB", CONTEXT)[1] < CONTEXT.ball_z  # weak side: away from the tight end


def test_depth_charts_use_each_teams_latest_snapshot_before_the_game_and_best_slot_first():
    rows = [
        {
            "dt": "2026-10-01",
            "team": "JAX",
            "espn_id": "9",
            "pos_grp": "3WR 1TE",
            "pos_abb": "WR",
            "pos_rank": 1,
        },
        {
            "dt": "2026-10-31",
            "team": "JAX",
            "espn_id": "9",
            "pos_grp": "Base 4-3 D",
            "pos_abb": "LCB",
            "pos_rank": 1,
        },
        {
            "dt": "2026-10-31",
            "team": "JAX",
            "espn_id": "9",
            "pos_grp": "3WR 1TE",
            "pos_abb": "WR",
            "pos_rank": 2,
        },
        {
            "dt": "2026-10-31",
            "team": "JAX",
            "espn_id": "9",
            "pos_grp": "Special Teams",
            "pos_abb": "KR",
            "pos_rank": 1,
        },
        {
            "dt": "2026-11-05",
            "team": "JAX",
            "espn_id": "9",
            "pos_grp": "3WR 1TE",
            "pos_abb": "WR",
            "pos_rank": 1,
        },
    ]
    assert A.from_depth_charts(rows, before="2026-11-02") == {"9": ("LCB", "WR", "KR")}
    # A two-way player lines up where his side of the ball has him.
    assert A.pick(("LCB", "WR", "KR"), "offense") == "WR"
    assert A.pick(("LCB", "WR", "KR"), "defense") == "LCB"
    assert A.pick(("FS",), "offense") is None  # a safety on the punt team has no base spot


@pytest.mark.parametrize("name", SCRIPTED)
def test_everyone_with_a_position_starts_where_it_lines_up_and_clear_of_the_others(name):
    made = placed(name)
    los = made.lines[0].x
    for actor in made.actors:
        if actor.espn_id:
            codes = POSITIONS[actor.espn_id]
            job = next((c for c in _ROLE_SLOTS.get(actor.role, ()) if c in codes), None)
            assert actor.position == (job or A.pick(codes, actor.side) or codes[0]), actor.key
        kind = A.group(actor.position)
        first = actor.segments[0]
        if kind is None or made.template in KICKS or actor.role in ("returner", "blocker"):
            continue
        if (kind in A.DEFENSE) != (actor.side == "defense"):
            continue
        low, high = BOXES[kind]
        assert low - 1e-6 <= first.x0 - los <= high + 1e-6, (
            actor.key,
            actor.position,
            first.x0 - los,
        )
    starts = [(a.key, a.segments[0].x0, a.segments[0].z0) for a in made.actors]
    for index, (key, x, z) in enumerate(starts):
        for other, ox, oz in starts[index + 1 :]:
            assert math.hypot(x - ox, z - oz) >= 0.9, (key, other)


@pytest.mark.parametrize("name", SCRIPTED)
def test_positions_keep_every_other_rule(name):
    """Natural motion, the snap and the sides of the line hold with positions as without."""
    made = placed(name)
    los = made.lines[0].x
    for actor in made.actors:
        x0 = actor.segments[0].x0
        if made.template == "kickoff" and actor.side == "offense":
            assert x0 <= los + 25 + 1e-6
        elif actor.side == "offense":
            assert x0 <= los + 1e-6
        elif actor.role != "returner":
            assert los - 1e-6 <= x0 <= los + 20 + 1e-6
        early = [s for s in actor.segments if s.pose in ("RUN", "DROP") and s.start < SNAP - 1e-6]
        assert not early or actor.role == "penalized", actor.key
    assert placed(name) == made  # the same play, positions and all, gives the same script


def test_the_fumble_lines_up_jackson_beside_the_center_and_lawrence_on_the_edge():
    made, play = placed("fumble_recovered_and_returned"), facts("fumble_recovered_and_returned")
    los, ball_z = made.lines[0].x, made.ball[0].at[2]
    by_id = {a.espn_id: a for a in made.actors}
    jackson, lawrence = by_id["3930040"], by_id["16802"]
    assert jackson.position == "RG" and lawrence.position == "WOLB"
    # Chicago's right guard: on the line, a man to the center's right (the far side).
    assert jackson.segments[0].x0 == pytest.approx(los - 0.6)
    assert 0.5 < jackson.segments[0].z0 - ball_z < 3.0
    # Seattle's 3-4 weakside linebacker rushes off the edge: on the line, outside the tackle.
    assert lawrence.segments[0].x0 == pytest.approx(los + 1.0)
    assert abs(lawrence.segments[0].z0 - ball_z) > 4.0
    assert by_id["4372020"].position == "RCB"
    assert play.fumble.lost


def test_a_defender_on_a_pass_drops_into_coverage_when_there_is_time():
    made = placed("pass_incomplete_qb_hit")
    defender = next(a for a in made.actors if a.key == "defender")
    first = next(
        s
        for s in defender.segments
        if s.start >= SNAP and s.pose not in ("ready", "drop_a", "drop_b", "drop_c")
    )
    assert first.pose in ("DROP", "RUN")
    if first.pose == "DROP":
        assert first.x1 > first.x0 and first.facing == "left"  # backpedalling, facing the passer


def test_without_positions_nothing_changes():
    for name in ("run_gap", "sack", "pass_without_yards_after_catch"):
        unplaced = script(name)
        assert all(a.position is None for a in unplaced.actors)


def test_a_punter_who_also_holds_shows_as_the_punter_on_a_punt():
    punter = next(a for a in placed("home_punt_downed").actors if a.role == "punter")
    assert POSITIONS[punter.espn_id][0] == "H" and punter.position == "P"


@pytest.mark.parametrize("name", SCRIPTED)
def test_a_corner_or_nickel_back_on_a_pass_lines_up_over_its_receiver(name):
    """Owner review of the play-type clips: a defensive back named on a pass covered its target,
    so he starts over him, not across the field."""
    made = placed(name)
    receiver = next((a for a in made.actors if a.key == "receiver"), None)
    for actor in made.actors:
        if (
            receiver is None
            or A.group(actor.position) not in ("CB", "NB")
            or actor.side != "defense"
        ):
            continue
        assert abs(actor.segments[0].z0 - receiver.segments[0].z0) <= 1.3 + 1e-6, actor.key


@pytest.mark.parametrize("name", SCRIPTED)
def test_a_wide_receiver_lines_up_at_least_in_the_slot(name):
    """From reviewing the play-type clips: a receiver three yards from the ball reads
    as a tight end."""
    made = placed(name)
    ball_z = next(s.at[2] for s in made.ball if s.state == "rest")
    for actor in made.actors:
        if actor.position == "WR" and actor.role == "receiver":
            assert abs(actor.segments[0].z0 - ball_z) >= 6.0 - 1e-6, actor.key
