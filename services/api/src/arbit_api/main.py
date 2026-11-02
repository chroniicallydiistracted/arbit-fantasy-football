"""Health and optional local operator reads. Member application awaits authentication."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from arbit_core.config import load_league_config
from arbit_data.db import SCHEMA_REVISION
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import Engine, String, Uuid, column, create_engine, select, table, text
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from arbit_api.local_league import install_operator_routes
from arbit_api.member_routes import install_member_routes
from arbit_api.settings import RuntimeSettings
from arbit_api.static_shell import install_static_shell


def create_app(settings: RuntimeSettings | None = None, *, engine: Engine | None = None) -> FastAPI:
    settings = settings or RuntimeSettings()
    config = load_league_config(settings.league_config_path)
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
                code = "SCHEMA_NOT_READY"
                with database.connect() as connection:
                    schema = connection.scalar(text("SELECT current_schema()"))
                    if isinstance(schema, str):
                        version_table = table(
                            "alembic_version", column("version_num", String), schema=schema
                        )
                        snapshot_table = table("league_snapshot", column("id", Uuid), schema=schema)
                        revision = connection.scalar(select(version_table.c.version_num))
                        connection.execute(select(snapshot_table.c.id).limit(0))
                        if settings.auth_mode != "disabled":
                            for name in (
                                "member_account",
                                "member_invitation",
                                "member_session",
                                "member_flow",
                                "member_binding",
                                "member_preferences",
                                "member_audit",
                            ):
                                connection.execute(
                                    select(1).select_from(table(name, schema=schema)).limit(0)
                                )
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

    install_operator_routes(app, settings, database, config.season)
    install_member_routes(app, settings, database, config.season)
    install_static_shell(app, settings.web_dist_path, settings.public_origin)
    return app
