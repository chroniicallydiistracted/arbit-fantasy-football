"""Exercise the actual HTTP stack through a loopback test server."""

import hashlib
import json
import socket
import threading
import time
from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit
from urllib.request import HTTPSHandler, ProxyHandler, Request, build_opener

import pytest
from arbit_data.espn import transport as module
from arbit_data.espn.transport import EspnError, EspnTransport


@contextmanager
def server(monkeypatch, *, body=b'{"points":0.1}', status=200, headers=None, delay=0):
    received = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            received.append((self.path, self.headers))
            time.sleep(delay)
            self.send_response(status)
            if "Content-Type" not in (headers or {}):
                self.send_header("Content-Type", "application/json")
            for key, value in (headers or {}).items():
                self.send_header(key, value)
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def log_message(self, *args):
            pass

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=lambda: httpd.serve_forever(poll_interval=0.01), daemon=True)
    thread.start()

    class Loopback(HTTPSHandler):
        def https_open(self, req):
            original = urlsplit(req.full_url)
            local = Request(
                f"http://127.0.0.1:{httpd.server_port}{original.path}?{original.query}",
                headers=dict(req.header_items()),
            )
            local.timeout = req.timeout
            return self.do_open(HTTPConnection, local)

    client = EspnTransport()
    # Replace only the network destination; keep request validation, pacing,
    # urllib error processing, redirect denial, size limits and JSON parsing real.
    client._opener = build_opener(ProxyHandler({}), module._NoRedirect(), Loopback())
    real_connect = socket.create_connection

    def local_only(address, *args, **kwargs):
        assert address[0] == "127.0.0.1", "Tests must never contact ESPN"
        return real_connect(address, *args, **kwargs)

    monkeypatch.setattr(socket, "create_connection", local_only)
    ticks = [0.0]
    monkeypatch.setattr(module, "monotonic", lambda: ticks[0])
    monkeypatch.setattr(module, "sleep", lambda seconds: ticks.__setitem__(0, ticks[0] + seconds))
    try:
        yield client, received, ticks
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join()


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
