"""Motion anchors and continuous movement, independently of any provider."""


def test_path_hits_anchors_and_keeps_velocity_through_a_turn():
    from arbit_data.live.trajectory import MotionAnchor, path, sample

    anchors = (
        MotionAnchor(t=0.0, x=20.0, z=23.0),
        MotionAnchor(t=1.0, x=24.0, z=25.0),
        MotionAnchor(t=2.0, x=28.0, z=23.0),
    )
    track = path(anchors)
    at_cut = sample(track, 1.0)
    assert (at_cut.x, at_cut.z, at_cut.vx, at_cut.vz) == (24, 25, 4, 0)
    before, after = sample(track, 0.999), sample(track, 1.001)
    assert abs(before.vx - after.vx) < 0.02
    assert before.vz > 0 > after.vz
    assert max(before.z, after.z) <= 25


def test_started_and_stopped_actors_hold_terminal_anchors():
    from arbit_data.live.trajectory import MotionAnchor, path, sample

    track = path(
        (
            MotionAnchor(t=0.6, x=24, z=28),
            MotionAnchor(t=2.0, x=32, z=27),
        )
    )
    assert (sample(track, 0).x, sample(track, 0).vx) == (24, 0)
    assert (sample(track, 2.5).x, sample(track, 2.5).vx) == (32, 0)
    assert 24 < sample(track, 1.0).x < 32


def test_body_facing_is_independent_of_travel_direction():
    import math

    from arbit_data.live.trajectory import MotionAnchor, path, sample

    track = path(
        (
            MotionAnchor(t=0.0, x=30, z=25, heading=math.pi),
            MotionAnchor(t=1.0, x=34, z=25, heading=math.pi),
        )
    )
    moving = sample(track, 0.5)
    assert moving.vx > 0 and moving.heading == math.pi


def test_speed_bound_catches_the_faster_middle_of_a_cubic():
    from arbit_data.live.trajectory import MotionAnchor, path, within_speed

    track = path((MotionAnchor(t=0, x=0, z=0), MotionAnchor(t=1, x=8, z=0)))
    assert not within_speed(track, 11)
    assert within_speed(track, 12.1)
