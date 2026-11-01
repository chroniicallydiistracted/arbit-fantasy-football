"""Local signed provider simulation; these tests do not prove a real provider login."""

from datetime import UTC, datetime
from urllib.parse import parse_qs, urlsplit

import pytest
from joserfc import jwt
from joserfc.errors import JoseError
from joserfc.jwk import RSAKey


def provider_settings():
    from arbit_api.settings import RuntimeSettings

    return RuntimeSettings(
        environment="test",
        auth_mode="oidc",
        public_origin="http://localhost:8000",
        database_url="postgresql+psycopg://unused:unused@127.0.0.1/arbit_test",
        oidc_issuer="https://identity.example",
        oidc_client_id="client",
        oidc_client_secret="test-client-secret",
        oidc_authorization_endpoint="https://identity.example/authorize",
        oidc_token_endpoint="https://identity.example/token",
        oidc_jwks_uri="https://identity.example/keys",
        oidc_allowed_hosts=("identity.example",),
    )


def test_signed_id_token_checks_signature_issuer_audience_nonce_expiry_and_email():
    from arbit_api.oidc import OidcClient

    key = RSAKey.generate_key(2048, parameters={"kid": "local-test-key"})
    other = RSAKey.generate_key(2048, parameters={"kid": "local-test-key"})
    keys = {"keys": [key.as_dict(private=False)]}
    now = int(datetime.now(UTC).timestamp())
    claims = {
        "iss": "https://identity.example",
        "sub": "subject-one",
        "aud": "client",
        "iat": now,
        "exp": now + 300,
        "nonce": "browser-nonce",
        "email": "one@example.test",
        "email_verified": True,
    }
    client = OidcClient(provider_settings())

    def token(values, signing_key=key):
        return {
            "id_token": jwt.encode({"alg": "RS256", "kid": "local-test-key"}, values, signing_key),
            "access_token": "local-access-token",
        }

    assert client.validate(token(claims), keys, "browser-nonce")["sub"] == "subject-one"
    for override in [
        {"iss": "https://attacker.example"},
        {"aud": "other-client"},
        {"nonce": "wrong"},
        {"nonce_supported": False, "nonce": "wrong"},
        {"exp": now - 120},
        {"iat": now + 300},
        {"email_verified": False},
        {"at_hash": "wrong"},
    ]:
        with pytest.raises((JoseError, ValueError)):
            client.validate(token({**claims, **override}), keys, "browser-nonce")
    with pytest.raises((JoseError, ValueError)):
        client.validate(token(claims, other), keys, "browser-nonce")
    with pytest.raises((JoseError, ValueError)):
        client.validate(
            {"id_token": jwt.encode({"alg": "HS256"}, claims, b"a" * 32)}, keys, "browser-nonce"
        )


def test_authorization_request_uses_pkce_s256_and_nonce():
    from arbit_api.oidc import OidcClient

    client = OidcClient(provider_settings())
    url = client.authorization_url({"state": "state", "nonce": "nonce", "verifier": "v" * 43})
    query = parse_qs(urlsplit(url).query)
    assert query["response_type"] == ["code"]
    assert query["nonce"] == ["nonce"]
    assert query["code_challenge_method"] == ["S256"]
    assert query["code_challenge"][0] != "v" * 43


def test_unsafe_oidc_configuration_is_rejected():
    from pydantic import ValidationError

    values = provider_settings().model_dump()
    for override in [
        {"oidc_token_endpoint": "https://attacker.example/token"},
        {"oidc_jwks_uri": "http://identity.example/keys"},
        {"oidc_issuer": "https://user:secret@identity.example"},
        {"environment": "production", "public_origin": "http://localhost:8000"},
    ]:
        with pytest.raises(ValidationError):
            provider_settings().__class__(**{**values, **override})


def test_provider_http_rejects_redirects_and_oversized_bodies():
    import httpx2
    from arbit_api.oidc import MAX_PROVIDER_BYTES, bounded_json

    for response in [
        httpx2.Response(302, headers={"location": "https://attacker.example"}),
        httpx2.Response(200, content=b"x" * (MAX_PROVIDER_BYTES + 1)),
    ]:
        transport = httpx2.MockTransport(lambda request, response=response: response)
        with httpx2.Client(transport=transport, follow_redirects=False, trust_env=False) as client:
            with pytest.raises((ValueError, httpx2.HTTPStatusError)):
                bounded_json(client, "GET", "https://identity.example/keys")


def test_at_hash_cannot_skip_validation_when_access_token_is_missing():
    from arbit_api.oidc import OidcClient

    key = RSAKey.generate_key(2048, parameters={"kid": "local-test-key"})
    now = int(datetime.now(UTC).timestamp())
    claims = {
        "iss": "https://identity.example",
        "sub": "subject",
        "aud": "client",
        "iat": now,
        "exp": now + 300,
        "nonce": "nonce",
        "email": "one@example.test",
        "email_verified": True,
        "at_hash": "wrong",
    }
    token = {"id_token": jwt.encode({"alg": "RS256", "kid": "local-test-key"}, claims, key)}
    with pytest.raises((JoseError, ValueError)):
        OidcClient(provider_settings()).validate(
            token, {"keys": [key.as_dict(private=False)]}, "nonce"
        )


def test_exchange_uses_bounded_fixed_endpoints_and_does_not_send_access_token_to_jwks(monkeypatch):
    import httpx2
    from arbit_api.oidc import BoundedOAuthClient, OidcClient

    key = RSAKey.generate_key(2048, parameters={"kid": "local-test-key"})
    now = int(datetime.now(UTC).timestamp())
    claims = {
        "iss": "https://identity.example",
        "sub": "subject",
        "aud": "client",
        "iat": now,
        "exp": now + 300,
        "nonce": "nonce",
        "email": "one@example.test",
        "email_verified": True,
    }
    calls = []

    def provider(request):
        calls.append(request)
        if request.url.path == "/token":
            body = parse_qs(request.content.decode())
            assert body["code_verifier"] == ["v" * 43]
            assert body["code"] == ["test-code"]
            return httpx2.Response(
                200,
                json={
                    "access_token": "provider-access-token",
                    "token_type": "Bearer",
                    "expires_in": 300,
                    "id_token": jwt.encode({"alg": "RS256", "kid": "local-test-key"}, claims, key),
                },
            )
        assert request.url.path == "/keys"
        assert "authorization" not in request.headers
        return httpx2.Response(200, json={"keys": [key.as_dict(private=False)]})

    settings = provider_settings()
    client = OidcClient(settings)
    monkeypatch.setattr(
        client,
        "_client",
        lambda: BoundedOAuthClient(
            "client",
            "test-client-secret",
            redirect_uri="http://localhost:8000/auth/callback",
            token_endpoint_auth_method="client_secret_post",
            transport=httpx2.MockTransport(provider),
            follow_redirects=False,
            trust_env=False,
            timeout=10,
        ),
    )
    assert (
        client.exchange("test-code", {"nonce": "nonce", "verifier": "v" * 43})["sub"] == "subject"
    )
    assert len(calls) == 2


def test_selected_google_profile_uses_fixed_endpoints_openid_scopes_and_pkce_without_network():
    from arbit_api.oidc import OidcClient
    from arbit_api.settings import RuntimeSettings

    values = provider_settings().model_dump()
    values.update(
        oidc_issuer="https://accounts.google.com",
        oidc_authorization_endpoint="https://accounts.google.com/o/oauth2/v2/auth",
        oidc_token_endpoint="https://oauth2.googleapis.com/token",
        oidc_jwks_uri="https://www.googleapis.com/oauth2/v3/certs",
        oidc_allowed_hosts=("accounts.google.com", "oauth2.googleapis.com", "www.googleapis.com"),
        oidc_client_id="fictional-client.apps.googleusercontent.com",
    )
    settings = RuntimeSettings(**values)
    url = OidcClient(settings).authorization_url(
        {"state": "s" * 43, "nonce": "n" * 43, "verifier": "v" * 43}
    )
    parsed = urlsplit(url)
    assert parsed.hostname == "accounts.google.com"
    assert parsed.path == "/o/oauth2/v2/auth"
    query = parse_qs(parsed.query)
    assert set(query["scope"][0].split()) == {"openid", "email", "profile"}
    assert query["code_challenge_method"] == ["S256"]
    assert query["nonce"] == ["n" * 43]
    assert query["client_id"] == ["fictional-client.apps.googleusercontent.com"]
