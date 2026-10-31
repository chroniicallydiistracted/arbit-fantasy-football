"""Bounded original JSON captures using the existing elapsed-deadline HTTP stack."""

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal, DecimalException
from http.client import HTTPException
from time import monotonic
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener

from arbit_data.errors import SourceError
from arbit_data.espn.http_deadline import DeadlineHTTPSHandler
from arbit_data.espn.transport import (
    SourceReceipt,
    _invalid_constant,
    _NoRedirect,
    _object,
    _retry_after,
    utc_now,
)
from arbit_data.public_sources.requests import SourceRequest, validate_request

MAX_BYTES = 32 * 1024 * 1024
TIMEOUT_SECONDS = 30.0


@dataclass(frozen=True)
class PublicResponse:
    body: bytes
    payload: dict[str, Any] | list[Any]
    receipt: SourceReceipt


def decode_json(body: bytes) -> dict[str, Any] | list[Any]:
    try:
        value = json.loads(
            body.decode("utf-8"),
            parse_float=Decimal,
            parse_constant=_invalid_constant,
            object_pairs_hook=_object,
        )
    except (ValueError, UnicodeError, RecursionError, DecimalException):
        raise SourceError("INVALID_JSON") from None
    if not isinstance(value, (dict, list)):
        raise SourceError("INVALID_RESPONSE")
    stack = [(value, 0)]
    nodes = 0
    while stack:
        item, depth = stack.pop()
        nodes += 1
        if depth > 64:
            raise SourceError("JSON_DEPTH_LIMIT")
        if nodes > 2_000_000:
            raise SourceError("JSON_NODE_LIMIT")
        if isinstance(item, dict):
            stack.extend((child, depth + 1) for child in item.values())
        elif isinstance(item, list):
            stack.extend((child, depth + 1) for child in item)
    return value


class PublicTransport:
    def __init__(self) -> None:
        self._opener = build_opener(ProxyHandler({}), _NoRedirect(), DeadlineHTTPSHandler())

    def fetch(self, request: SourceRequest) -> PublicResponse:
        request = validate_request(request)
        started = monotonic()
        try:
            with self._opener.open(
                Request(
                    request.url,
                    headers={
                        "User-Agent": "Arbit/0.1 public read-only sources",
                        "Accept": "application/json",
                        "Accept-Encoding": "identity",
                    },
                    method="GET",
                ),
                timeout=TIMEOUT_SECONDS,
            ) as response:
                if (
                    response.status != 200
                    or response.headers.get_content_type() != "application/json"
                    or response.headers.get("Content-Encoding", "identity").lower() != "identity"
                ):
                    raise SourceError("INVALID_RESPONSE")
                length = response.headers.get("Content-Length")
                if length is not None:
                    if len(length) > 20 or not length.isascii() or not length.isdigit():
                        raise SourceError("INVALID_RESPONSE")
                    if int(length) > MAX_BYTES:
                        raise SourceError("RESPONSE_TOO_LARGE")
                body = bytearray()
                while True:
                    if monotonic() - started >= TIMEOUT_SECONDS:
                        raise SourceError("NETWORK_ERROR")
                    chunk = response.read1(min(65536, MAX_BYTES + 1 - len(body)))
                    if not chunk:
                        break
                    body.extend(chunk)
                    if len(body) > MAX_BYTES:
                        raise SourceError("RESPONSE_TOO_LARGE")
                if length is not None and int(length) != len(body):
                    raise SourceError("INVALID_RESPONSE")
        except HTTPError as error:
            status = error.code
            retry = _retry_after(error.headers.get("Retry-After"))
            error.close()
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
            raise SourceError(code, status=status, retry_after_seconds=retry) from None
        except (URLError, OSError, HTTPException):
            raise SourceError("NETWORK_ERROR") from None
        data = bytes(body)
        payload = decode_json(data)
        if not isinstance(payload, dict if request.response_kind == "object" else list):
            raise SourceError("INVALID_RESPONSE")
        return PublicResponse(
            data,
            payload,
            SourceReceipt(request.url, utc_now(), hashlib.sha256(data).hexdigest(), len(data)),
        )
