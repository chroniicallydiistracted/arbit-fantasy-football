"""Reproducible schema export. No database connection, provider call or server startup."""

import json
from pathlib import Path

from arbit_api.main import create_app
from arbit_api.settings import RuntimeSettings


def export() -> str:
    app = create_app(
        RuntimeSettings(
            environment="test",
            auth_mode="fixture",
            public_origin="http://localhost:8000",
            database_url="postgresql+psycopg://unused:unused@127.0.0.1/arbit_fixture",
        )
    )
    return json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n"


if __name__ == "__main__":
    destination = Path("packages/contracts/openapi.json")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(export())
    print(f"Exported {destination}")
