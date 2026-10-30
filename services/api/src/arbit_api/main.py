"""Health-only service composition. Private league routes await member authentication."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from arbit_core.config import load_league_config
from arbit_data.db import SCHEMA_REVISION
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from arbit_api.settings import RuntimeSettings


def create_app(settings: RuntimeSettings | None = None, *, engine: Engine | None = None) -> FastAPI:
    settings = settings or RuntimeSettings()
    load_league_config(settings.league_config_path)
    owns_engine = engine is None
    database = engine
    if database is None and settings.database_url is not None:
        database = create_engine(
            settings.database_url.get_secret_value(),
            hide_parameters=True,
            connect_args={"connect_timeout": 3},
            pool_pre_ping=True,
        )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            if owns_engine and database is not None:
                database.dispose()

    app = FastAPI(
        title="Arbit API",
        version="0.1.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    headers = {"Cache-Control": "no-store"}

    @app.get("/health/live")
    def live() -> JSONResponse:
        return JSONResponse({"status": "alive"}, headers=headers)

    @app.get("/health/ready")
    def ready() -> JSONResponse:
        code = "DATABASE_NOT_CONFIGURED"
        if database is not None:
            try:
                with database.connect() as connection:
                    revision = connection.scalar(text("SELECT version_num FROM alembic_version"))
                    connection.execute(text("SELECT id FROM league_snapshot LIMIT 0"))
                if revision == SCHEMA_REVISION:
                    return JSONResponse({"status": "ready"}, headers=headers)
                code = "SCHEMA_MISMATCH"
            except OperationalError:
                code = "DATABASE_UNAVAILABLE"
            except SQLAlchemyError:
                code = "SCHEMA_NOT_READY"
        return JSONResponse(
            {"status": "unavailable", "code": code}, status_code=503, headers=headers
        )

    return app
