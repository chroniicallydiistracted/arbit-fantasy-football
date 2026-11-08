"""A play's natural phases fitted to its real snap-to-whistle time (OWN-052)."""

import pytest
from arbit_data.live.timing import Phase, fit

RUN = (
    Phase("mesh", 0.45, 0.6, 1.3),
    Phase("path", 0.5, 0.8, 2.2),
    Phase("gain", 0.7, 0.7, 0.7),  # the yards at the carrier's own pace: fixed
    Phase("dead", 0.4, 0.6, 1.5),
)
NATURAL = 0.6 + 0.8 + 0.7 + 0.6
MOST = 1.3 + 2.2 + 0.7 + 1.5
LEAST = 0.45 + 0.5 + 0.7 + 0.4


def test_without_a_real_time_every_phase_keeps_its_natural_length():
    fitted = fit(RUN, None)
    assert fitted.seconds == {"mesh": 0.6, "path": 0.8, "gain": 0.7, "dead": 0.6}
    assert fitted.unfilled == fitted.over == 0.0


def test_a_longer_play_grows_each_phase_by_the_same_share_of_its_room():
    fitted = fit(RUN, 4.0)
    assert sum(fitted.seconds.values()) == pytest.approx(4.0)
    shares = {
        p.name: (fitted.seconds[p.name] - p.natural) / (p.most - p.natural)
        for p in RUN
        if p.most > p.natural
    }
    assert len(set(round(s, 9) for s in shares.values())) == 1
    assert fitted.seconds["gain"] == 0.7
    assert fitted.unfilled == fitted.over == 0.0


def test_time_beyond_every_phases_most_is_reported_not_hidden():
    fitted = fit(RUN, MOST + 1.25)
    assert fitted.seconds == {p.name: p.most for p in RUN}
    assert fitted.unfilled == pytest.approx(1.25)
    assert fitted.over == 0.0


def test_a_shorter_play_shrinks_phases_toward_their_least():
    budget = (NATURAL + LEAST) / 2
    fitted = fit(RUN, budget)
    assert sum(fitted.seconds.values()) == pytest.approx(budget)
    assert all(p.least <= fitted.seconds[p.name] <= p.natural for p in RUN)


def test_a_play_shorter_than_its_least_plan_overruns_by_the_difference():
    fitted = fit(RUN, LEAST - 0.3)
    assert fitted.seconds == {p.name: p.least for p in RUN}
    assert fitted.over == pytest.approx(0.3)
    assert fitted.unfilled == 0.0


def test_phases_must_be_ordered_least_natural_most():
    with pytest.raises(ValueError):
        Phase("bad", 1.0, 0.5, 2.0)
