"""Exercise the actual HTTP stack through a loopback test server."""

import hashlib
import json
import time
from datetime import UTC, datetime
from decimal import Decimal
from urllib.parse import parse_qs, urlsplit

import pytest
from arbit_data.espn import transport as module
from arbit_data.espn.transport import EspnError
from espn_http import server


def test_public_get_exact_numbers_receipt_and_pacing(monkeypatch):
    with server(monkeypatch) as (client, received, ticks):
        first = client.get(2026, views=("mRoster", "mSettings"), scoring_period=8)
        second = client.get(
            2026, views=("kona_player_info",), fantasy_filter={"players": {"offset": 300}}
        )
        assert first.payload == {"points": Decimal("0.1")}
        assert first.receipt.sha256 == hashlib.sha256(b'{"points":0.1}').hexdigest()
        assert first.receipt.byte_count == 14
        assert first.receipt.observed_at.utcoffset().total_seconds() == 0
        assert first.receipt.url.startswith("https://lm-api-reads.fantasy.espn.com/")
        query = parse_qs(urlsplit(received[0][0]).query)
        assert query == {"view": ["mRoster", "mSettings"], "scoringPeriodId": ["8"]}
        assert urlsplit(received[0][0]).path.endswith("/2026/segments/0/leagues/1729878439")
        assert "Cookie" not in received[0][1] and "Authorization" not in received[0][1]
        assert received[0][1]["Accept-Encoding"] == "identity"
        assert json.loads(received[1][1]["X-Fantasy-Filter"]) == {"players": {"offset": 300}}
        assert second.receipt.fantasy_filter == '{"players":{"offset":300}}'
        assert ticks[0] >= 2.0


@pytest.mark.parametrize(
    "status,code",
    [
        (401, "ACCESS_DENIED"),
        (403, "ACCESS_DENIED"),
        (404, "NOT_FOUND"),
        (429, "RATE_LIMITED"),
        (503, "UNAVAILABLE"),
    ],
)
def test_http_errors_are_safe_and_never_retried(monkeypatch, status, code):
    with server(monkeypatch, status=status, body=b"PRIVATE owner password") as (
        client,
        received,
        _,
    ):
        with pytest.raises(EspnError) as caught:
            client.get(2026, views=("mSettings",))
        assert caught.value.code == code
        assert caught.value.status == status
        assert "PRIVATE" not in str(caught.value)
        assert len(received) == 1


@pytest.mark.parametrize(
    "header,expected", [("120", 120), ("Fri, 30 Oct 2026 12:02:00 GMT", 120), ("nonsense", None)]
)
def test_retry_after_is_preserved_without_early_retry(monkeypatch, header, expected):
    monkeypatch.setattr(module, "utc_now", lambda: datetime(2026, 10, 30, 12, tzinfo=UTC))
    with server(monkeypatch, status=429, headers={"Retry-After": header}) as (client, received, _):
        with pytest.raises(EspnError) as caught:
            client.get(2026, views=("mSettings",))
        assert caught.value.retry_after_seconds == expected
        with pytest.raises(EspnError) as again:
            client.get(2026, views=("mRoster",))
        assert again.value.code == "RATE_LIMITED"
        assert len(received) == 1


@pytest.mark.parametrize(
    "body,headers,code",
    [
        (b"<html>login</html>", {"Content-Type": "text/html"}, "INVALID_RESPONSE"),
        (b'{"x":NaN}', {}, "INVALID_JSON"),
        (b'{"x":1,"x":2}', {}, "INVALID_JSON"),
        (b'{"x":', {}, "INVALID_JSON"),
        (b"[]", {}, "INVALID_RESPONSE"),
        (b"{}", {"Content-Encoding": "gzip"}, "INVALID_RESPONSE"),
        (b"x" * 65, {}, "RESPONSE_TOO_LARGE"),
        (b"{}", {"Content-Length": "65"}, "RESPONSE_TOO_LARGE"),
        pytest.param(
            b"{}", {"Content-Length": "9" * 5000}, "INVALID_RESPONSE", id="absurd-content-length"
        ),
    ],
)
def test_bad_responses_cannot_become_data(monkeypatch, body, headers, code):
    monkeypatch.setattr(module, "MAX_BYTES", 64)
    with server(monkeypatch, body=body, headers=headers) as (client, _, _):
        with pytest.raises(EspnError) as caught:
            client.get(2026, views=("mSettings",))
        assert caught.value.code == code


def test_redirect_is_not_followed(monkeypatch):
    with server(monkeypatch, status=302, headers={"Location": "http://127.0.0.1:1/collect"}) as (
        client,
        received,
        _,
    ):
        with pytest.raises(EspnError) as caught:
            client.get(2026, views=("mSettings",))
        assert caught.value.code == "REDIRECT_DENIED"
        assert len(received) == 1


def test_timeout_is_typed(monkeypatch):
    monkeypatch.setattr(module, "TIMEOUT_SECONDS", 0.02)
    with server(monkeypatch, delay=0.06) as (client, received, _):
        with pytest.raises(EspnError) as caught:
            client.get(2026, views=("mSettings",))
        assert caught.value.code == "NETWORK_ERROR"
        assert len(received) == 1


@pytest.mark.parametrize(
    "season,views,period",
    [
        (2025, ("mSettings",), None),
        (True, ("mSettings",), None),
        (2026, ("unknown",), None),
        (2026, ("mSettings",), 0),
        (2026, ("mSettings",), True),
    ],
)
def test_invalid_scope_fails_before_network(monkeypatch, season, views, period):
    with server(monkeypatch) as (client, received, _):
        with pytest.raises(ValueError):
            client.get(season, views=views, scoring_period=period)
        assert received == []


@pytest.mark.parametrize(
    "chunks",
    [
        [b"HTTP/1.1 200 OK\r\nX-Slow: "]
        + [b"x"] * 20
        + [b"\r\nContent-Type: application/json\r\n\r\n{}"],
        [
            b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nTransfer-Encoding: chunked\r\n\r\n1;"
        ]
        + [b"x"] * 20
        + [b"\r\nx\r\n0\r\n\r\n"],
    ],
)
def test_elapsed_deadline_bounds_dribbled_headers_and_chunk_framing(monkeypatch, chunks):
    monkeypatch.setattr(module, "TIMEOUT_SECONDS", 0.1)
    with server(monkeypatch, raw_chunks=chunks, delay=0.04, real_clock=True) as (client, _, _):
        started = time.monotonic()
        with pytest.raises(EspnError) as caught:
            client.get(2026, views=("mSettings",))
        elapsed = time.monotonic() - started
        assert caught.value.code == "NETWORK_ERROR"
        assert elapsed < 0.45


def test_decimal_parse_failure_is_a_safe_provider_error(monkeypatch):
    with server(monkeypatch, body=b'{"x":1e9999999999999999999999}') as (client, _, _):
        with pytest.raises(EspnError) as caught:
            client.get(2026, views=("mSettings",))
        assert caught.value.code == "INVALID_JSON"
