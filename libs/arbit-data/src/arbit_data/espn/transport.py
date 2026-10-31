"""Bounded GET-only public ESPN transport. No credentials or automatic retries."""

import hashlib
import json
import math
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, DecimalException
from email.utils import parsedate_to_datetime
from http.client import HTTPException
from time import monotonic, sleep
from typing import Any, Literal
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from arbit_data.espn.endpoints import Endpoint, EndpointOptions, build_request
from arbit_data.espn.http_deadline import DeadlineHTTPSHandler

MAX_BYTES = 8 * 1024 * 1024
TIMEOUT_SECONDS = 15.0


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


@dataclass(frozen=True)
class EndpointFetchResult:
    payload: dict[str, Any] | list[Any] | bytes
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
        self._opener = build_opener(ProxyHandler({}), _NoRedirect(), DeadlineHTTPSHandler())
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
        if not views:
            raise ValueError("At least one league view required")
        result = self.fetch(
            Endpoint.LEAGUE,
            EndpointOptions(
                season=season,
                views=views,
                scoring_period=scoring_period,
                fantasy_filter=fantasy_filter,
            ),
        )
        if not isinstance(result.payload, dict):
            raise EspnError("INVALID_RESPONSE")
        return FetchResult(result.payload, result.receipt)

    def fetch(self, endpoint: Endpoint, options: EndpointOptions) -> EndpointFetchResult:
        spec = build_request(endpoint, options)
        filter_json = spec.fantasy_filter
        headers = {
            "Accept": "application/json",
            "Accept-Encoding": "identity",
            "User-Agent": "Arbit/0.1 (FFA public read-only)",
        }
        if filter_json is not None:
            headers["X-Fantasy-Filter"] = filter_json
        request = Request(spec.url, headers=headers, method="GET")
        with self._lock:
            if monotonic() < self._blocked_until:
                raise EspnError(
                    "RATE_LIMITED",
                    status=429,
                    retry_after_seconds=math.ceil(self._blocked_until - monotonic()),
                )
            sleep(max(0.0, self._next_request_at - monotonic()))
            self._next_request_at = monotonic() + 2.0
            return self._fetch(request, filter_json, spec.response_format)

    def _fetch(
        self,
        request: Request,
        filter_json: str | None,
        response_format: Literal["object", "array", "png"],
    ) -> EndpointFetchResult:
        started = monotonic()
        try:
            with self._opener.open(request, timeout=TIMEOUT_SECONDS) as response:
                if response.status != 200:
                    raise EspnError("INVALID_RESPONSE", status=response.status)
                if (
                    response.headers.get_content_type()
                    != ("image/png" if response_format == "png" else "application/json")
                    or response.headers.get("Content-Encoding", "identity").lower() != "identity"
                ):
                    raise EspnError("INVALID_RESPONSE")
                length = response.headers.get("Content-Length")
                if length is not None:
                    if len(length) > 20 or not length.isascii() or not length.isdigit():
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
        if response_format == "png":
            if not body.startswith(b"\x89PNG\r\n\x1a\n"):
                raise EspnError("INVALID_RESPONSE")
            return EndpointFetchResult(
                bytes(body),
                SourceReceipt(
                    request.full_url,
                    utc_now(),
                    hashlib.sha256(body).hexdigest(),
                    len(body),
                    filter_json,
                ),
            )
        try:
            payload = json.loads(
                body.decode("utf-8"),
                parse_float=Decimal,
                parse_constant=_invalid_constant,
                object_pairs_hook=_object,
            )
        except (ValueError, UnicodeError, RecursionError, DecimalException):
            raise EspnError("INVALID_JSON") from None
        if not isinstance(payload, dict if response_format == "object" else list):
            raise EspnError("INVALID_RESPONSE")
        return EndpointFetchResult(
            payload,
            SourceReceipt(
                request.full_url,
                utc_now(),
                hashlib.sha256(body).hexdigest(),
                len(body),
                filter_json,
            ),
        )
