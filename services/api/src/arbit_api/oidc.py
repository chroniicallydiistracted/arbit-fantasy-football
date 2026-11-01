"""Fixed-provider OIDC using Authlib OAuth and maintained JOSE/claim validation.

No discovery, redirects, environment proxies, provider token persistence or logs.
The only accepted signature algorithm is RS256; keys come from the configured
JWKS endpoint, never token-controlled jku/x5u URLs.
"""

import json
import time
from typing import Any, cast
from urllib.parse import parse_qsl

import httpx2
from authlib.integrations.httpx_client import OAuth2Client  # type: ignore[import-untyped]
from authlib.oidc.core import CodeIDToken  # type: ignore[import-untyped]
from joserfc import jwt
from joserfc.jwk import KeySet, KeySetSerialization

from arbit_api.settings import RuntimeSettings

MAX_PROVIDER_BYTES = 262144


def bounded_json(client: httpx2.Client, method: str, url: str, **kwargs: Any) -> dict[str, Any]:
    start = time.monotonic()
    with client.stream(method, url, **kwargs) as response:
        response.raise_for_status()
        body = bytearray()
        if response.headers.get("content-encoding", "identity") != "identity":
            raise ValueError("PROVIDER_ENCODING_UNSUPPORTED")
        for chunk in response.iter_bytes(chunk_size=65536):
            body.extend(chunk)
            if len(body) > MAX_PROVIDER_BYTES or time.monotonic() - start > 10:
                raise ValueError("PROVIDER_RESPONSE_LIMIT")
        result = json.loads(body)
        if not isinstance(result, dict):
            raise ValueError("PROVIDER_RESPONSE_INVALID")
        return result


class BoundedOAuthClient(OAuth2Client):  # type: ignore[misc]
    def _fetch_token(
        self,
        url: str,
        body: str = "",
        headers: Any = None,
        auth: Any = None,
        method: str = "POST",
        **kwargs: Any,
    ) -> Any:
        token = bounded_json(
            self, method, url, data=dict(parse_qsl(body)), headers=headers, auth=auth, **kwargs
        )
        return self.parse_response_token(httpx2.Response(200, json=token))


class OidcClient:
    def __init__(self, settings: RuntimeSettings) -> None:
        self.settings = settings

    def _client(self) -> BoundedOAuthClient:
        return BoundedOAuthClient(
            self.settings.oidc_client_id,
            self.settings.oidc_client_secret.get_secret_value()
            if self.settings.oidc_client_secret
            else None,
            scope="openid email profile",
            redirect_uri=f"{self.settings.public_origin}/auth/callback",
            code_challenge_method="S256",
            token_endpoint_auth_method="client_secret_post",
            timeout=10,
            follow_redirects=False,
            trust_env=False,
            headers={"Accept-Encoding": "identity"},
        )

    def authorization_url(self, flow: dict[str, str]) -> str:
        with self._client() as client:
            url, _ = client.create_authorization_url(
                self.settings.oidc_authorization_endpoint,
                state=flow["state"],
                nonce=flow["nonce"],
                code_verifier=flow["verifier"],
            )
            return str(url)

    def exchange(self, code: str, flow: dict[str, Any]) -> dict[str, Any]:
        with self._client() as client:
            token = client.fetch_token(
                self.settings.oidc_token_endpoint,
                grant_type="authorization_code",
                code=code,
                code_verifier=flow["verifier"],
            )
            keys = bounded_json(
                client, "GET", str(self.settings.oidc_jwks_uri), withhold_token=True
            )
            return self.validate(token, keys, flow["nonce"])

    def validate(self, token: dict[str, Any], keys: dict[str, Any], nonce: str) -> dict[str, Any]:
        decoded = jwt.decode(
            token["id_token"],
            KeySet.import_key_set(cast(KeySetSerialization, keys)),
            algorithms=["RS256"],
        )
        if "at_hash" in decoded.claims and (
            not decoded.claims["at_hash"]
            or not isinstance(token.get("access_token"), str)
            or not token["access_token"]
        ):
            raise ValueError("SIGN_IN_DENIED")
        claims = CodeIDToken(
            decoded.claims,
            decoded.header,
            options={
                "iss": {"essential": True, "value": self.settings.oidc_issuer},
                "aud": {"essential": True, "value": self.settings.oidc_client_id},
                "email": {"essential": True},
                "email_verified": {"essential": True, "value": True},
            },
            params={
                "nonce": nonce,
                "client_id": self.settings.oidc_client_id,
                "access_token": token.get("access_token"),
            },
        )
        claims.validate(leeway=30)
        if (
            claims.get("email_verified") is not True
            or not isinstance(claims.get("email"), str)
            or not isinstance(claims.get("sub"), str)
            or not nonce
        ):
            raise ValueError("SIGN_IN_DENIED")
        return dict(claims)
