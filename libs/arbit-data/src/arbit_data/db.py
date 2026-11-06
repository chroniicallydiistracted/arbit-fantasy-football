"""Database boundary; every publication/job mutation owns a real transaction."""

from dataclasses import dataclass

from sqlalchemy import Engine

SCHEMA_REVISION = "0008_nfl_api"


@dataclass(frozen=True)
class UnitOfWork:
    engine: Engine
