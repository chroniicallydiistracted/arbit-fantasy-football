"""Migration execution without rendering connection strings or credentials."""

import os

from alembic import context
from sqlalchemy import create_engine


def run(connection):
    context.configure(connection=connection)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    raise RuntimeError("Use an explicit local database for migrations")
elif context.config.attributes.get("connection") is not None:
    run(context.config.attributes["connection"])
else:
    url = os.environ.get("ARBIT_DATABASE_URL")
    if not url:
        raise RuntimeError("ARBIT_DATABASE_URL is required for migration execution")
    engine = create_engine(url, hide_parameters=True)
    try:
        with engine.connect() as connection:
            run(connection)
    finally:
        engine.dispose()
