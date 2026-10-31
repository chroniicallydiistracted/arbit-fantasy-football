"""Public source requests must stay fixed, bounded and reproducible."""

import hashlib
from dataclasses import replace

import pytest
from arbit_data.errors import SourceError
from espn_http import server


def test_source_routes_are_scoped_and_cannot_accept_injected_paths():
    from arbit_data.public_sources.requests import build_source_request, validate_request

    assert build_source_request("sleeper.players").ttl_seconds == 86400
    assert build_source_request("sleeper.trending.add").usage == "supplemental"
    assert build_source_request("sleeper.stats.v1", week=7).usage == "candidate"
    req = build_source_request("espn.plays", event_id="401873023", page=2)
    assert "page=2" in req.url
    for kw in ({"event_id": "1/../../secret"}, {"event_id": "123", "page": 0}):
        with pytest.raises(ValueError):
            build_source_request("espn.plays", **kw)
    with pytest.raises(ValueError):
        validate_request(replace(req, url="https://evil.example/a"))
    with pytest.raises(ValueError):
        build_source_request("sleeper.league")


def test_public_transport_preserves_original_bytes_and_rejects_redirects(monkeypatch):
    from arbit_data.public_sources.requests import build_source_request
    from arbit_data.public_sources.transport import PublicTransport

    req = build_source_request("sleeper.state")
    with server(
        monkeypatch, body=b'{"season":"2026","zero":0.1}', headers={"Content-Length": "28"}
    ) as (client, _, _):
        t = PublicTransport()
        t._opener = client._opener
        result = t.fetch(req)
        assert result.receipt.sha256 == hashlib.sha256(result.body).hexdigest()
        assert str(result.payload["zero"]) == "0.1"
    with server(monkeypatch, status=302, headers={"Location": "https://evil.example/"}) as (
        client,
        _,
        _,
    ):
        t = PublicTransport()
        t._opener = client._opener
        with pytest.raises(SourceError, match="REDIRECT_DENIED"):
            t.fetch(req)


@pytest.mark.parametrize("body", [b'{"a":1,"a":2}', b'{"a":NaN}', b"[", b"null"])
def test_public_transport_rejects_invalid_json(monkeypatch, body):
    from arbit_data.public_sources.requests import build_source_request
    from arbit_data.public_sources.transport import PublicTransport

    with server(monkeypatch, body=body) as (client, _, _):
        t = PublicTransport()
        t._opener = client._opener
        with pytest.raises(SourceError):
            t.fetch(build_source_request("sleeper.state"))


def test_public_transport_length_limit_and_retry_hint(monkeypatch):
    from arbit_data.public_sources.requests import build_source_request
    from arbit_data.public_sources.transport import PublicTransport

    req = build_source_request("sleeper.state")
    with server(monkeypatch, headers={"Content-Length": "999999999"}) as (client, _, _):
        t = PublicTransport()
        t._opener = client._opener
        with pytest.raises(SourceError, match="RESPONSE_TOO_LARGE"):
            t.fetch(req)
    with server(monkeypatch, status=429, headers={"Retry-After": "120"}) as (client, _, _):
        t = PublicTransport()
        t._opener = client._opener
        with pytest.raises(SourceError) as e:
            t.fetch(req)
        assert e.value.retry_after_seconds == 120
