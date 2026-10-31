"""Bounded GET-only public ESPN transport. No credentials or automatic retries."""

import hashlib
import json
import math
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from email.utils import parsedate_to_datetime
from http.client import HTTPException
from time import monotonic, sleep
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

MAX_BYTES = 8 * 1024 * 1024
TIMEOUT_SECONDS = 15.0
ORIGIN = "https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl"
VIEWS = frozenset(
    {
        "mSettings",
        "mTeam",
        "mRoster",
        "mMatchupScore",
        "mDraftDetail",
        "mStatus",
        "kona_player_info",
    }
)


def utc_now() -> datetime:
    return datetime.now(UTC)


class EspnError(Exception):
    """Safe failure metadata; never stores request headers or response content."""

    def __init__(
        self, code: str, *, status: int | None = None, retry_after_seconds: int | None = None
    ):
        self.code = code
        self.status = status
        self.retry_after_seconds = retry_after_seconds
        super().__init__(code)


@dataclass(frozen=True)
class SourceReceipt:
    url: str
    observed_at: datetime
    sha256: str
    byte_count: int
    fantasy_filter: str | None = None


@dataclass(frozen=True)
class FetchResult:
    payload: dict[str, Any]
    receipt: SourceReceipt


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        return None


def _retry_after(value: str | None) -> int | None:
    if value is None or len(value) > 128:
        return None
    value = value.strip()
    if value.isascii() and value.isdigit():
        return int(value)
    try:
        target = parsedate_to_datetime(value)
        if target.tzinfo is None:
            return None
        return max(0, math.ceil((target - utc_now()).total_seconds()))
    except (ValueError, TypeError, OverflowError):
        return None


def _object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def _invalid_constant(value: str) -> None:
    raise ValueError("Nonfinite JSON value")


class EspnTransport:
    """Serial 30/minute budget per instance; scheduled multi-process sync is not yet supported."""

    def __init__(self) -> None:
        self._opener = build_opener(ProxyHandler({}), _NoRedirect())
        self._lock = threading.Lock()
        self._next_request_at = 0.0
        self._blocked_until = 0.0

    def get(
        self,
        season: int,
        *,
        views: tuple[str, ...],
        scoring_period: int | None = None,
        fantasy_filter: dict[str, object] | None = None,
    ) -> FetchResult:
        if type(season) is not int or not 2026 <= season <= 2100:
            raise ValueError("Explicit supported season required")
        if not views or any(view not in VIEWS for view in views) or len(set(views)) != len(views):
            raise ValueError("Unsupported or duplicate ESPN view")
        if scoring_period is not None and (
            type(scoring_period) is not int or not 1 <= scoring_period <= 99
        ):
            raise ValueError("Scoring period must be an integer from 1 to 99")
        parameters = [("view", view) for view in views]
        if scoring_period is not None:
            parameters.append(("scoringPeriodId", str(scoring_period)))
        url = f"{ORIGIN}/seasons/{season}/segments/0/leagues/1729878439?{urlencode(parameters)}"
        filter_json = (
            None
            if fantasy_filter is None
            else json.dumps(fantasy_filter, separators=(",", ":"), sort_keys=True, allow_nan=False)
        )
        if filter_json is not None and len(filter_json) > 8192:
            raise ValueError("Fantasy filter exceeds size limit")
        headers = {
            "Accept": "application/json",
            "Accept-Encoding": "identity",
            "User-Agent": "Arbit/0.1 (FFA public read-only)",
        }
        if filter_json is not None:
            headers["X-Fantasy-Filter"] = filter_json
        request = Request(url, headers=headers, method="GET")
        with self._lock:
            if monotonic() < self._blocked_until:
                raise EspnError(
                    "RATE_LIMITED",
                    status=429,
                    retry_after_seconds=math.ceil(self._blocked_until - monotonic()),
                )
            sleep(max(0.0, self._next_request_at - monotonic()))
            self._next_request_at = monotonic() + 2.0
            return self._fetch(request, filter_json)

    def _fetch(self, request: Request, filter_json: str | None) -> FetchResult:
        started = monotonic()
        try:
            with self._opener.open(request, timeout=TIMEOUT_SECONDS) as response:
                if response.status != 200:
                    raise EspnError("INVALID_RESPONSE", status=response.status)
                if (
                    response.headers.get_content_type() != "application/json"
                    or response.headers.get("Content-Encoding", "identity").lower() != "identity"
                ):
                    raise EspnError("INVALID_RESPONSE")
                length = response.headers.get("Content-Length")
                if length is not None:
                    if not length.isascii() or not length.isdigit():
                        raise EspnError("INVALID_RESPONSE")
                    if int(length) > MAX_BYTES:
                        raise EspnError("RESPONSE_TOO_LARGE")
                body = bytearray()
                while True:
                    if monotonic() - started >= TIMEOUT_SECONDS:
                        raise EspnError("NETWORK_ERROR")
                    chunk = response.read1(min(64 * 1024, MAX_BYTES + 1 - len(body)))
                    if not chunk:
                        break
                    body.extend(chunk)
                    if len(body) > MAX_BYTES:
                        raise EspnError("RESPONSE_TOO_LARGE")
                if length is not None and len(body) != int(length):
                    raise EspnError("INVALID_RESPONSE")
        except HTTPError as error:
            status = error.code
            retry = _retry_after(error.headers.get("Retry-After"))
            error.close()
            if status == 429:
                self._blocked_until = monotonic() + (60 if retry is None else retry)
            code = (
                "ACCESS_DENIED"
                if status in (401, 403)
                else "NOT_FOUND"
                if status == 404
                else "RATE_LIMITED"
                if status == 429
                else "REDIRECT_DENIED"
                if 300 <= status < 400
                else "UNAVAILABLE"
                if status >= 500
                else "HTTP_ERROR"
            )
            raise EspnError(code, status=status, retry_after_seconds=retry) from None
        except (URLError, OSError, HTTPException):
            raise EspnError("NETWORK_ERROR") from None
        try:
            payload = json.loads(
                body.decode("utf-8"),
                parse_float=Decimal,
                parse_constant=_invalid_constant,
                object_pairs_hook=_object,
            )
        except (ValueError, UnicodeError, RecursionError):
            raise EspnError("INVALID_JSON") from None
        if not isinstance(payload, dict):
            raise EspnError("INVALID_RESPONSE")
        return FetchResult(
            payload,
            SourceReceipt(
                request.full_url,
                utc_now(),
                hashlib.sha256(body).hexdigest(),
                len(body),
                filter_json,
            ),
        )
