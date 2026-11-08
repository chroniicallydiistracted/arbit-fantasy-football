"""Play scripts for kicks, tries, fumbles and penalties (automation slice 3), from real ESPN plays."""

import math

import pytest
from arbit_data.live.choreography import FIELD_WIDTH, PlayScript
from arbit_data.live.kicking import CROSSBAR, END_LINE, HOLD, KICKOFF_SETUP, POST_HALF, POST_Z
from arbit_data.live.kicking import choreograph_try as kick_try
from live_cases import at, facts, script


def actor(made: PlayScript, key: str):
    return next(a for a in made.actors if a.key == key)


def flights(made: PlayScript):
    return [s for s in made.ball if s.state == "flight"]


def kick_flight(made: PlayScript):
    """The kick itself: the longest flight."""
    return max(flights(made), key=lambda s: s.end - s.start)


def crossing(made: PlayScript):
    return next(
        (
            s.target.point
            for s in flights(made)
            if s.target.point and s.target.point[0] == pytest.approx(END_LINE)
        ),
        None,
    )


def resting_at_end(made: PlayScript):
    last = max(made.ball, key=lambda s: s.start)
    return last.at if last.state == "rest" else None


# Field goals and tries ---------------------------------------------------------------------------


def test_a_good_field_goal_goes_between_the_uprights_above_the_bar_into_the_net():
    made = script("field_goal_good")
    cross = crossing(made)
    assert cross is not None
    assert abs(cross[2] - POST_Z) < POST_HALF and cross[1] > CROSSBAR
    assert resting_at_end(made)[0] > END_LINE  # it ends behind the posts, in the net
    assert kick_flight(made).spin == "tumble"  # end over end
    kicker = actor(made, "kicker")
    assert {s.pose for s in kicker.segments} >= {"kick_strike", "arms_up"}


def test_the_hold_is_eight_yards_behind_the_line_and_the_unit_is_named_from_the_text():
    play, made = facts("field_goal_good"), script("field_goal_good")
    teed = next(s for s in made.ball if s.state == "rest" and s.spin == "upright")
    assert teed.at[0] == pytest.approx(play.start - HOLD + 0.4)
    snapper, holder = actor(made, "snapper"), actor(made, "holder")
    assert snapper.label == "S.Daly"
    assert holder.label == "T.Taylor" and holder.segments[0].x0 == pytest.approx(play.start - HOLD)
    assert actor(made, "kicker").label == "C.Santos"


def test_a_long_snapper_without_an_espn_id_appears_under_the_texts_name():
    snapper = actor(script("home_punt_downed"), "snapper")
    assert snapper.espn_id is None and snapper.label == "C.Stoll"


def test_a_kick_wide_right_passes_outside_the_far_upright():
    cross = crossing(script("field_goal_wide_right"))
    assert cross is not None and cross[2] > POST_Z + POST_HALF


def test_a_blocked_kick_comes_off_the_blocker_and_never_reaches_the_posts():
    play, made = facts("field_goal_blocked"), script("field_goal_blocked")
    assert crossing(made) is None
    assert resting_at_end(made)[0] < play.start + 10
    blocker = actor(made, "blocker")
    assert blocker.side == "defense" and blocker.label == "A.Booker"
    assert "kick_follow" in {s.pose for s in actor(made, "kicker").segments}
    assert "arms_up" not in {s.pose for s in actor(made, "kicker").segments}


def test_the_extra_point_is_its_own_play_from_the_15_and_wide_left_passes_on_the_near_side():
    play = facts("pass_catch_spot_and_missed_pat")
    made = kick_try(play, "try")
    assert made is not None and made.template == "extra_point"
    assert made.lines[0].x == 85  # snapped from the 15, the goal line at 100
    cross = crossing(made)
    assert cross is not None and cross[2] < POST_Z - POST_HALF  # the kicker's left: near side
    assert actor(made, "kicker").label == "J.Myers"  # named from the try, not the touchdown
    assert "No Good, Wide Left" in made.caption and "Center-" not in made.caption


def test_a_two_point_pass_is_caught_in_the_end_zone_by_the_player_who_scored_it():
    play = facts("two_point_success")
    made = kick_try(play, "try")
    assert made is not None and made.template == "two_point"
    assert made.lines[0].x == 98
    receiver = actor(made, "receiver")
    assert receiver.espn_id == next(p.espn_id for p in play.players if p.role == "patScorer")
    assert receiver.label == "J.Addison" and receiver.segments[-1].x1 >= 100
    assert "ATTEMPT SUCCEEDS" in made.caption


def test_no_try_without_a_touchdown():
    assert kick_try(facts("run_gap"), "try") is None


# Punts -------------------------------------------------------------------------------------------


def test_a_punt_is_snapped_15_yards_and_spirals_to_the_returner_who_runs_to_espns_spot():
    play, made = facts("away_punt_returned"), script("away_punt_returned")
    punter = actor(made, "punter")
    assert punter.segments[0].x0 == pytest.approx(play.start - 15)
    kick = kick_flight(made)
    assert kick.spin == "spiral" and kick.target.actor == "returner"
    returner = actor(made, "returner")
    assert at(returner.segments, kick.end - 1e-3).pose.startswith("catch_high")
    assert at(returner.segments, kick.end - 1e-3).x1 == pytest.approx(play.kick.landing, abs=1.6)
    assert returner.segments[-1].x1 == pytest.approx(play.action_end, abs=0.05)
    tackler = actor(made, "tackler_1")
    assert tackler.side == "offense" and tackler.label == "J.Walker"  # the kicking team tackles
    assert actor(made, "snapper").label == "S.Daly"


def test_a_fair_catch_is_signalled_and_not_returned():
    made = script("punt_fair_catch")
    returner = actor(made, "returner")
    kick = kick_flight(made)
    poses = [s.pose for s in returner.segments if s.end <= kick.end + 1e-6]
    assert "arms_up" in poses
    assert not any(a.role == "tackler" for a in made.actors)
    assert max(made.ball, key=lambda s: s.start).actor == "returner"  # he keeps the ball


def test_a_downed_punt_comes_to_rest_where_espn_spots_it():
    play, made = facts("home_punt_downed"), script("home_punt_downed")
    assert kick_flight(made).target.point[0] == pytest.approx(play.kick.landing)
    assert resting_at_end(made)[0] == pytest.approx(play.kick.landing, abs=3.0)


def test_a_touchback_rests_in_the_end_zone_and_the_flag_is_thrown_during_the_kick():
    made = script("punt_touchback_with_penalty")
    assert resting_at_end(made)[0] > 100
    (flag,) = made.props
    kick = kick_flight(made)
    assert kick.start < flag.start < kick.end
    assert "Illegal Block Above the Waist" in made.caption


# Kickoffs ----------------------------------------------------------------------------------------


def test_a_kickoff_tumbles_off_the_tee_and_the_coverage_waits_at_the_40_until_the_catch():
    play, made = facts("kickoff_returned"), script("kickoff_returned")
    tee = next(s for s in made.ball if s.state == "rest")
    assert tee.spin == "upright" and tee.at[0] == pytest.approx(play.start)
    kick = kick_flight(made)
    assert kick.spin == "tumble" and kick.target.actor == "returner"
    tackler = actor(made, "tackler_1")
    waiting = [s for s in tackler.segments if s.end <= kick.end + 1e-6]
    line = play.start + KICKOFF_SETUP  # the receiving 40 (OWN-035)
    assert waiting and all(line - 1.5 <= s.x1 <= line + 0.3 for s in waiting)
    assert actor(made, "returner").segments[-1].x1 == pytest.approx(play.action_end, abs=0.05)


def test_a_kickoff_touchback_comes_down_in_the_end_zone():
    made = script("kickoff_touchback")
    assert resting_at_end(made)[0] > 100
    assert not any(a.role == "returner" for a in made.actors)


def test_a_kickoff_out_of_bounds_lands_past_a_sideline_and_draws_a_flag_there():
    made = script("kickoff_out_of_bounds")
    landing = kick_flight(made).target.point
    assert landing[2] < 0 or landing[2] > FIELD_WIDTH
    (flag,) = made.props
    assert flag.start >= kick_flight(made).end and 0 <= flag.at[2] <= FIELD_WIDTH
    assert "Kickoff Out of Bounds" in made.caption


def test_an_onside_kick_is_short_and_low():
    play, made = facts("kickoff_onside"), script("kickoff_onside")
    kick = kick_flight(made)
    assert kick.end - kick.start < 1.5
    assert actor(made, "returner").label == "R.Flournoy"
    assert play.kick.onside


# Fumbles -----------------------------------------------------------------------------------------


def test_a_fumble_comes_loose_at_the_hit_and_the_recoverer_falls_on_it_at_espns_spot():
    play, made = facts("fumble_lost"), script("fumble_lost")
    assert made.template == "fumble"
    receiver = actor(made, "receiver")
    hit = next(s for s in receiver.segments if s.pose == "hit")
    loose = [s for s in flights(made) if s.start >= hit.start]
    assert loose and loose[0].origin.actor == "receiver"
    assert loose[-1].end - loose[0].start >= 0.35  # it squirts out, it doesn't teleport
    assert all(s.spin == "tumble" for s in loose)
    rest = next(s for s in made.ball if s.state == "rest" and s.start >= loose[-1].end - 1e-6)
    assert rest.at[0] == pytest.approx(play.fumble.spot)
    recoverer = actor(made, "recoverer")
    assert recoverer.side == "defense" and recoverer.label == "J.Brents"
    held = max(made.ball, key=lambda s: s.start)
    assert held.state == "held" and held.actor == "recoverer"
    diving = at(recoverer.segments, held.start - 1e-3)
    assert diving.pose == "tackle_dive"
    assert math.hypot(diving.x1 - rest.at[0], diving.z1 - rest.at[2]) < 0.5
    assert "FUMBLES" in made.caption and "J.Brents" in made.caption


def test_the_player_who_forced_the_fumble_is_the_tackler_and_appears_once():
    play, made = facts("fumble_lost"), script("fumble_lost")
    forcer = next(p.espn_id for p in play.players if p.role == "forcedBy")
    drawn = [a for a in made.actors if a.espn_id == forcer]
    assert len(drawn) == 1 and drawn[0].role == "tackler"


def test_a_tackler_who_forces_and_recovers_it_stays_up_scoops_it_and_is_tackled_on_the_return():
    play, made = facts("fumble_recovered_and_returned"), script("fumble_recovered_and_returned")
    forcer = next(p.espn_id for p in play.players if p.role == "forcedBy")
    (lawrence,) = [a for a in made.actors if a.espn_id == forcer]
    poses = [s.pose for s in lawrence.segments]
    assert "drive" in poses and poses.index("catch_low") > poses.index("drive")
    assert "fall_60" not in poses[: poses.index("catch_low")]  # he never went down with the tackle
    held = max(made.ball, key=lambda s: s.start)
    assert held.state == "held" and held.actor == lawrence.key
    assert lawrence.segments[-1].x1 == pytest.approx(play.action_end, abs=0.05)
    returner_tackler = actor(made, "return_tackler_1")
    assert returner_tackler.side == "offense" and returner_tackler.label == "J.Jackson"
    # CHI's J.Jackson, the guard (ESPN 3930040, flagged for a false start earlier in the game),
    # lines up on Chicago's side of the line, not past it near a sideline (OWN-035).
    assert returner_tackler.segments[0].x0 <= made.lines[0].x
    assert "RECOVERED by SEA-D.Lawrence, to CHI 25 for no gain" in made.caption


# Penalties ---------------------------------------------------------------------------------------


def test_a_foul_before_the_snap_shows_the_player_and_a_flag_at_the_line():
    play, made = facts("no_play_penalty"), script("no_play_penalty")
    assert made.template == "penalty"
    (player,) = [a for a in made.actors if a.role != "official"]
    assert player.role == "penalized" and player.label == "D.Walker" and player.side == "defense"
    assert player.segments[-1].x1 < play.start  # an encroachment: across the line
    (flag,) = made.props
    # Tossed by the nearest official: a sideline official, or the umpire within a few yards.
    assert (
        flag.origin[2] < 0 or flag.origin[2] > FIELD_WIDTH or abs(flag.origin[0] - flag.at[0]) <= 8
    )
    assert flag.land - flag.start < 1.0
    assert abs(flag.at[0] - play.start) < 3 and flag.land > flag.start
    assert "No Play" in made.caption
    assert max(made.ball, key=lambda s: s.start).state == "rest"  # the ball never moves


def test_a_declined_penalty_still_shows_its_flag():
    made = script("declined_penalty")
    (flag,) = made.props
    assert 0 <= flag.at[2] <= FIELD_WIDTH and -10 <= flag.at[0] <= 110
    assert flag.land - flag.start < 1.0  # a short toss, not a throw across the field
    assert "Offensive Holding, declined" in made.caption


def test_a_play_wiped_out_by_a_flag_is_drawn_with_the_flag_and_called_no_play():
    made = script("penalty_wipes_out_pass")
    assert made.template == "penalty"
    assert {a.role for a in made.actors} >= {"passer", "receiver"}
    (flag,) = made.props
    release = next(s for s in made.ball if s.state == "flight").start
    assert flag.start > release - 1.0  # interference: thrown as the ball is in the air
    assert flag.at[0] > made.lines[0].x  # downfield, where the receiver was
    assert made.caption.endswith("Defensive Pass Interference · No Play")


def test_a_delay_of_game_is_the_ball_the_lines_and_a_flag():
    play, made = facts("delay_of_game"), script("delay_of_game")
    # No player: the ball, the lines, and the official who throws the flag (OWN-037).
    assert [a.role for a in made.actors] == ["official"]
    (flag,) = made.props
    assert abs(flag.at[0] - play.start) < 3
    assert {s.state for s in made.ball} == {"rest"}


@pytest.mark.parametrize("name", ["home_punt_downed", "field_goal_good", "fumble_lost"])
def test_plays_without_a_penalty_have_no_flag(name):
    assert script(name).props == ()


def test_lateral_stops_the_recreation_at_the_verified_first_catch():
    from arbit_data.live.choreography import choreograph

    clip = choreograph(facts("lateral"), "verified-lateral")
    assert clip is not None and clip.note
    assert (
        len(
            [
                segment
                for segment in clip.ball
                if segment.target and segment.target.actor == "receiver"
            ]
        )
        == 1
    )
    assert next(a for a in clip.actors if a.key == "receiver").segments[-1].x1 == 24
