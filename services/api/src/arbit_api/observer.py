"""The read-only dev account: a signed-in view of the running app, for checking it.

    uv run --env-file .env.local --env-file .env.auth.local python -m arbit_api.observer session
    uv run --env-file .env.local --env-file .env.auth.local python -m arbit_api.observer end

`session` creates the dev account if needed and gives it one new session, ending any earlier one.
It lasts 12 hours (`--hours` up to 24). The session goes only into a browser storage-state file
readable by this user alone, `data/observer/storage-state.json`, which Playwright loads; the token
is never printed. `end` ends every dev account session at once. The administrator can also end
them, or suspend the account, under Preferences → League access.

The dev account can open every team and the administrator pages and can change nothing but its
own preferences. The API refuses everything else, and ignores the account entirely when
ARBIT_ENV=production.
"""

import argparse
import json
import os
import sys
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlsplit

from arbit_data.db import UnitOfWork
from arbit_data.members import MemberError, end_observer_sessions, issue_observer_session
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError

from arbit_api.member_routes import COOKIE
from arbit_api.settings import RuntimeSettings

STATE = Path("data/observer/storage-state.json")


def write_state(path: Path, origin: str, token: str, expires: float) -> None:
    """Write a Playwright storage state holding the session cookie, readable by this user only."""
    host = urlsplit(origin).hostname or "127.0.0.1"
    state = {
        "cookies": [
            {
                "name": COOKIE,
                "value": token,
                "domain": host,
                "path": "/",
                "expires": expires,
                "httpOnly": True,
                "secure": origin.startswith("https://"),
                "sameSite": "Lax",
            }
        ],
        "origins": [],
    }
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    partial = path.with_suffix(".partial")
    partial.unlink(missing_ok=True)
    descriptor = os.open(partial, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "w") as file:
        json.dump(state, file)
    partial.replace(path)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="python -m arbit_api.observer")
    parser.add_argument("action", choices=("session", "end"))
    parser.add_argument("--hours", type=float, default=12.0)
    args = parser.parse_args(argv)
    settings = RuntimeSettings()
    if settings.environment == "production":
        print("The dev account is off in production.", file=sys.stderr)
        return 1
    if settings.auth_mode != "oidc" or not settings.database_url or not settings.public_origin:
        print(
            "Run with the running app's settings (.env.local and .env.auth.local).", file=sys.stderr
        )
        return 1
    engine = create_engine(settings.database_url.get_secret_value(), hide_parameters=True)
    uow = UnitOfWork(engine)
    try:
        if args.action == "end":
            ended = end_observer_sessions(uow)
            STATE.unlink(missing_ok=True)
            print(f"Ended {ended} dev account session(s).")
            return 0
        token, expires = issue_observer_session(uow, lifetime=timedelta(hours=args.hours))
        write_state(STATE, settings.public_origin, token, expires.timestamp())
        local = expires.astimezone().strftime("%Y-%m-%d %H:%M %Z")
        print(f"Dev account signed in until {local}. Session saved to {STATE} (this user only).")
        return 0
    except MemberError as error:
        reason = {
            "SIGN_IN_DENIED": "The dev account is suspended. Reactivate it under League access.",
            "INVALID_SESSION_LIFETIME": "--hours must be between 5 minutes (0.09) and 24.",
        }.get(str(error), f"Refused: {error}")
        print(reason, file=sys.stderr)
        return 1
    except SQLAlchemyError:
        print(
            "The database is unavailable. Is the dev database running? (`docker ps`)",
            file=sys.stderr,
        )
        return 1
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
