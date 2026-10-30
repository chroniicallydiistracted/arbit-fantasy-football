"""Server-only process settings. League facts live in the checked-in league config."""

from pathlib import Path
from typing import Literal, Self

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    @model_validator(mode="after")
    def validate_environment(self) -> Self:
        if self.environment == "production":
            if self.auth_bypass:
                raise ValueError("authentication bypass is forbidden in production")
            raise ValueError("production is unavailable until member authentication is implemented")
        if self.database_url and not self.database_url.get_secret_value().startswith(
            "postgresql+psycopg://"
        ):
            raise ValueError("database URL must use the PostgreSQL psycopg driver")
        return self
