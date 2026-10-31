"""Fixed read-only source resources; no caller-provided URL or embedded-reference fetching."""

from dataclasses import dataclass
from typing import Literal

from arbit_data.espn.endpoints import Endpoint, EndpointOptions, build_request


@dataclass(frozen=True)
class SourceRequest:
    kind: str
    provider: Literal["espn", "sleeper"]
    url: str
    response_kind: Literal["object", "array"]
    ttl_seconds: int
    usage: Literal["supplemental", "candidate", "live"]
    season: int = 2026
    week: int | None = None
    event_id: str | None = None
    page: int = 1
    season_type: int = 2

    @property
    def key(self) -> str:
        return self.url


def build_source_request(
    kind: str,
    *,
    season: int = 2026,
    week: int | None = None,
    event_id: str | None = None,
    page: int = 1,
    season_type: int = 2,
) -> SourceRequest:
    if (
        type(season) is not int
        or not 2026 <= season <= 2100
        or type(page) is not int
        or not 1 <= page <= 20
    ):
        raise ValueError("INVALID_SOURCE_SCOPE")
    if week is not None and (type(week) is not int or not 1 <= week <= 25):
        raise ValueError("INVALID_SOURCE_SCOPE")
    if type(season_type) is not int or season_type not in (1, 2, 3):
        raise ValueError("INVALID_SOURCE_SCOPE")
    if event_id is not None and (
        not isinstance(event_id, str)
        or not event_id.isascii()
        or not event_id.isdigit()
        or event_id.startswith("0")
        or len(event_id) > 20
    ):
        raise ValueError("INVALID_SOURCE_SCOPE")
    if kind.startswith("sleeper."):
        raise ValueError("SLEEPER_LIVE_ONLY")
    provider: Literal["espn", "sleeper"] = "espn"
    response: Literal["object", "array"] = "object"
    usage: Literal["supplemental", "candidate", "live"] = "live"
    if kind.startswith("espn."):
        provider = "espn"
        usage = "live"
        ttl = 30
        if kind == "espn.scoreboard":
            if week is None:
                raise ValueError("NFL_WEEK_REQUIRED")
            endpoint = Endpoint.NFL_SCOREBOARD
            options = EndpointOptions(season=season, nfl_week=week, season_type=season_type)
        elif kind == "espn.summary":
            endpoint = Endpoint.NFL_SUMMARY
            options = EndpointOptions(event_id=event_id)
        elif kind == "espn.plays":
            endpoint = Endpoint.NFL_PLAYS
            options = EndpointOptions(event_id=event_id, limit=300, page=page)
        else:
            raise ValueError("UNSUPPORTED_SOURCE")
        url = build_request(endpoint, options).url
    else:
        raise ValueError("UNSUPPORTED_SOURCE")
    if not kind.startswith("espn.") and (event_id is not None or page != 1):
        raise ValueError("INVALID_SOURCE_SCOPE")
    if kind != "espn.plays" and page != 1:
        raise ValueError("INVALID_SOURCE_SCOPE")
    if kind not in ("espn.summary", "espn.plays") and event_id is not None:
        raise ValueError("INVALID_SOURCE_SCOPE")
    return SourceRequest(
        kind, provider, url, response, ttl, usage, season, week, event_id, page, season_type
    )


def validate_request(request: SourceRequest) -> SourceRequest:
    expected = build_source_request(
        request.kind,
        season=request.season,
        week=request.week,
        event_id=request.event_id,
        page=request.page,
        season_type=request.season_type,
    )
    if request != expected:
        raise ValueError("INVALID_SOURCE_REQUEST")
    return expected
