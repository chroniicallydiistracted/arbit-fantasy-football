"""Owner policy: Sleeper is live NFL games/PBP only, with no eligible route enabled yet."""

import pytest


@pytest.mark.parametrize(
    "kind",
    [
        "sleeper.players",
        "sleeper.state",
        "sleeper.trending.add",
        "sleeper.trending.drop",
        "sleeper.stats.v1",
        "sleeper.stats.current",
        "sleeper.league",
        "sleeper.live.unverified",
    ],
)
def test_sleeper_noneligible_resources_are_blocked_before_request_construction(kind):
    from arbit_data.public_sources.requests import build_source_request

    with pytest.raises(ValueError, match="SLEEPER_LIVE_ONLY"):
        build_source_request(kind, week=7)


def test_retired_sleeper_request_cannot_read_a_cached_fantasy_capture(tmp_path):
    from arbit_data.nflverse.objects import ObjectStore
    from arbit_data.public_sources.requests import SourceRequest
    from arbit_data.public_sources.service import SourceService

    class NoIO:
        def fetch(self, request):
            raise AssertionError("No Sleeper network request is allowed")

    request = SourceRequest(
        "sleeper.players",
        "sleeper",
        "https://api.sleeper.app/v1/players/nfl",
        "object",
        86400,
        "supplemental",
    )
    service = SourceService(object(), ObjectStore(tmp_path), NoIO())
    with pytest.raises(ValueError, match="SLEEPER_LIVE_ONLY"):
        service.acquire(request, lambda p: p)
