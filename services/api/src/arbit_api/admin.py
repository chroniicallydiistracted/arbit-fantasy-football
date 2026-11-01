"""Safe first-administrator invitation. Never prints private invitation contents.

Configure server-only OIDC settings, migrate the database, then run
``uv run python -m arbit_api.admin``. The email is read without terminal echo.
The private fragment URL is written exclusively under ignored secrets/.
Further invitations/bindings/revocations use the authenticated admin API.
"""

import argparse
import getpass
import os
from pathlib import Path

from arbit_data.db import UnitOfWork
from arbit_data.members import MemberError, create_invitation
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError

from arbit_api.settings import RuntimeSettings


def write_bootstrap(settings: RuntimeSettings, email: str, output: Path) -> None:
    if settings.auth_mode != "oidc" or not settings.database_url or not settings.oidc_issuer:
        raise ValueError("Bootstrap requires complete server-only OIDC configuration")
    private_root = (Path.cwd() / "secrets").resolve()
    destination = output.resolve()
    if not destination.is_relative_to(private_root):
        raise ValueError("Invitation output must be inside ignored secrets/")
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    engine = create_engine(settings.database_url.get_secret_value(), hide_parameters=True)
    try:
        with os.fdopen(descriptor, "w") as file:
            token = create_invitation(
                UnitOfWork(engine), settings.oidc_issuer, email, role="admin", bootstrap=True
            )
            file.write(f"{settings.public_origin}/join#{token}\n")
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    finally:
        engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create the first private administrator invitation"
    )
    parser.add_argument("--output", type=Path, default=Path("secrets/admin-invitation.txt"))
    args = parser.parse_args()
    try:
        write_bootstrap(
            RuntimeSettings(),
            getpass.getpass("Invited administrator email (hidden): "),
            args.output,
        )
    except (ValueError, MemberError, SQLAlchemyError, OSError):
        raise SystemExit(
            "Bootstrap refused or unavailable. Verify safe OIDC settings, migration and unused private output path."
        ) from None
    print(
        "Private invitation saved under secrets/. Keep the file private; it expires in seven days."
    )


if __name__ == "__main__":
    main()
