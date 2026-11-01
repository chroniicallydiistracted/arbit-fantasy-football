"""Server-only process settings. League facts live in the checked-in league config."""

import re
from pathlib import Path
from typing import Literal, Self
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


class RuntimeSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ARBIT_", hide_input_in_errors=True, populate_by_name=True, extra="ignore"
    )

    environment: Literal["development", "test", "production"] = Field(
        default="development", validation_alias="ARBIT_ENV"
    )
    bind_host: str = "127.0.0.1"
    league_config_path: Path = Path("config/league.json")
    database_url: SecretStr | None = Field(default=None, repr=False)
    espn_s2: SecretStr | None = Field(default=None, repr=False)
    espn_swid: SecretStr | None = Field(default=None, repr=False)
    auth_bypass: bool = False
    auth_mode: Literal["disabled", "oidc", "fixture"] = "disabled"
    public_origin: str | None = None
    oidc_issuer: str | None = None
    oidc_client_id: str | None = None
    oidc_client_secret: SecretStr | None = Field(default=None, repr=False)
    oidc_authorization_endpoint: str | None = None
    oidc_token_endpoint: str | None = None
    oidc_jwks_uri: str | None = None
    oidc_allowed_hosts: tuple[str, ...] = ()
    web_dist_path: Path | None = Path("apps/web/dist")
    nflverse_path: Path = Path("data/nflverse")
    operator_token: SecretStr | None = Field(default=None, repr=False)

    @model_validator(mode="after")
    def validate_environment(self) -> Self:
        if self.auth_bypass:
            raise ValueError("authentication bypass is forbidden; use isolated fixture mode")
        if self.environment == "production" and self.auth_mode != "oidc":
            raise ValueError("production requires complete secure member authentication")
        if self.auth_mode != "disabled":
            if not self.database_url or not self.public_origin:
                raise ValueError("member authentication requires database and public origin")
            origin = urlsplit(self.public_origin)
            if (
                origin.username
                or origin.password
                or origin.path not in ("", "/")
                or origin.query
                or origin.fragment
                or not origin.hostname
            ):
                raise ValueError("public origin must be a fixed origin without credentials or path")
            self.public_origin = self.public_origin.rstrip("/")
            if self.environment == "production" and origin.scheme != "https":
                raise ValueError("production requires HTTPS")
            if origin.scheme not in ("http", "https") or (
                origin.scheme == "http"
                and origin.hostname not in ("127.0.0.1", "localhost", "::1", "testserver")
            ):
                raise ValueError("HTTP member authentication is loopback-only")
        if self.auth_mode == "fixture":
            db = make_url(self.database_url.get_secret_value()) if self.database_url else None
            if (
                self.environment != "test"
                or self.bind_host not in ("127.0.0.1", "::1", "localhost")
                or not db
                or db.host not in ("127.0.0.1", "localhost", "::1")
                or not (db.database or "").endswith(("_test", "_fixture"))
            ):
                raise ValueError(
                    "fixture authentication requires test environment and loopback dedicated _test/_fixture database"
                )
        if self.auth_mode == "oidc":
            if (
                not self.oidc_client_id
                or not self.oidc_client_secret
                or not self.oidc_client_secret.get_secret_value()
                or not self.oidc_allowed_hosts
            ):
                raise ValueError("OIDC requires complete fixed server configuration")
            for endpoint in (
                self.oidc_issuer,
                self.oidc_authorization_endpoint,
                self.oidc_token_endpoint,
                self.oidc_jwks_uri,
            ):
                url = urlsplit(endpoint or "")
                if (
                    url.scheme != "https"
                    or url.hostname not in self.oidc_allowed_hosts
                    or url.username
                    or url.password
                    or url.fragment
                    or url.port not in (None, 443)
                ):
                    raise ValueError(
                        "OIDC endpoints require HTTPS on explicitly allowed fixed provider hosts"
                    )
            if urlsplit(self.oidc_issuer or "").query:
                raise ValueError("OIDC issuer cannot contain a query")
        if self.database_url and not self.database_url.get_secret_value().startswith(
            "postgresql+psycopg://"
        ):
            raise ValueError("database URL must use the PostgreSQL psycopg driver")
        if self.operator_token is not None:
            if self.environment == "production":
                raise ValueError("local operator reads are unavailable in production")
            if not re.fullmatch(r"[A-Za-z0-9_-]{32,128}", self.operator_token.get_secret_value()):
                raise ValueError("operator token requires 32..128 URL-safe characters")
            if self.bind_host not in ("127.0.0.1", "::1", "localhost"):
                raise ValueError("local operator reads require a loopback bind")
        return self
