"""The read-only dev account on the running app: every team, administrator pages, no changes."""

import json
import stat
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

ORIGIN = "http://testserver"


def settings(engine, **changes):
    from arbit_api.settings import RuntimeSettings

    values = {
        "environment": "test",
        "database_url": engine.url.render_as_string(hide_password=False),
        "auth_mode": "fixture",
        "public_origin": ORIGIN,
    }
    return RuntimeSettings(**(values | changes))


def observer_client(app, token):
    client = TestClient(app, client=("127.0.0.1", 50000))
    client.cookies.set("arbit_session", token)
    return client


def test_dev_account_sees_every_team_and_changes_nothing(uow, engine):
    from arbit_api.fixture import seed
    from arbit_api.main import create_app
    from arbit_data.members import csrf_token, issue_observer_session

    configured = settings(engine)
    seed(configured, engine)
    token, expires = issue_observer_session(uow)
    assert timedelta(hours=11.9) < expires - datetime.now(UTC) <= timedelta(hours=12)
    write = {"Origin": ORIGIN, "X-CSRF-Token": csrf_token(token)}
    app = create_app(configured, engine=engine)
    with observer_client(app, token) as client:
        me = client.get("/api/v1/me").json()
        assert me["observer"] is True and me["account"]["role"] == "member"
        assert me["binding_status"] == "bound" and len(me["teams"]) == 2
        for team in me["teams"]:
            office = client.get("/api/v1/front-office", params={"team_id": team["id"]})
            assert office.status_code == 200 and office.json()["team"]["id"] == team["id"]
        assert client.get("/api/v1/admin/directory").status_code == 200
        refused = client.post(
            "/api/v1/admin/invitations",
            json={"email": "x@example.test", "role": "member"},
            headers=write,
        )
        assert refused.status_code == 403 and refused.json()["code"] == "OBSERVER_READ_ONLY"
        accounts = client.get("/api/v1/admin/directory").json()["accounts"]
        other = next(a for a in accounts if a["display_name"] != "Dev account (read-only)")
        for path, body in (
            ("/api/v1/admin/sessions/revoke", {"account_id": other["id"], "suspend": True}),
            (
                "/api/v1/admin/bindings",
                {"account_id": other["id"], "manager_id": other["manager_ids"][0]},
            ),
            ("/api/v1/me/sessions/revoke", {}),
        ):
            assert (
                client.post(path, json=body, headers=write).json()["code"] == "OBSERVER_READ_ONLY"
            )
        preferences = client.get("/api/v1/me").json()["preferences"]
        saved = client.put(
            "/api/v1/me/preferences", json={**preferences, "theme": "dark"}, headers=write
        )
        assert saved.status_code == 200
        assert client.post("/auth/logout", headers=write).status_code == 200
        assert client.get("/api/v1/me").status_code == 401
    # The other member is untouched by any of that.
    with engine.connect() as c:
        from arbit_data.member_schema import account

        assert c.execute(account.select().where(account.c.suspended.is_(True))).first() is None


def test_dev_account_sessions_end_and_respect_suspension(uow, engine):
    from arbit_api.fixture import seed
    from arbit_api.main import create_app
    from arbit_data.member_schema import account
    from arbit_data.members import (
        OBSERVER_ISSUER,
        MemberError,
        end_observer_sessions,
        issue_observer_session,
    )

    configured = settings(engine)
    seed(configured, engine)
    first, _ = issue_observer_session(uow)
    second, _ = issue_observer_session(uow)  # a new session ends the earlier one
    app = create_app(configured, engine=engine)
    with observer_client(app, first) as client:
        assert client.get("/api/v1/me").status_code == 401
    with observer_client(app, second) as client:
        assert client.get("/api/v1/me").status_code == 200
    assert end_observer_sessions(uow) == 1
    with observer_client(app, second) as client:
        assert client.get("/api/v1/me").status_code == 401
    with engine.begin() as c:
        c.execute(
            account.update().where(account.c.issuer == OBSERVER_ISSUER).values(suspended=True)
        )
    with pytest.raises(MemberError, match="SIGN_IN_DENIED"):
        issue_observer_session(uow)
    with pytest.raises(MemberError, match="INVALID_SESSION_LIFETIME"):
        issue_observer_session(uow, lifetime=timedelta(days=2))


def test_dev_account_is_ignored_in_production(uow, engine):
    from arbit_api.fixture import seed
    from arbit_api.main import create_app
    from arbit_data.members import issue_observer_session

    seed(settings(engine), engine)
    token, _ = issue_observer_session(uow)
    production = settings(
        engine,
        environment="production",
        auth_mode="oidc",
        public_origin="https://ffa.example.test",
        oidc_issuer="https://accounts.example.test",
        oidc_client_id="client",
        oidc_client_secret="secret",
        oidc_authorization_endpoint="https://accounts.example.test/auth",
        oidc_token_endpoint="https://accounts.example.test/token",
        oidc_jwks_uri="https://accounts.example.test/jwks",
        oidc_allowed_hosts=("accounts.example.test",),
    )
    app = create_app(production, engine=engine)
    with observer_client(app, token) as client:
        assert client.get("/api/v1/me").status_code == 401


def test_session_file_is_private_and_holds_only_the_cookie(tmp_path):
    from arbit_api.observer import write_state

    path = tmp_path / "observer" / "storage-state.json"
    write_state(path, "http://127.0.0.1:8000", "t" * 43, 1893456000.0)
    write_state(path, "http://127.0.0.1:8000", "u" * 43, 1893456000.0)  # replaces the old one
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
    [cookie] = json.loads(path.read_text())["cookies"]
    assert cookie == {
        "name": "arbit_session",
        "value": "u" * 43,
        "domain": "127.0.0.1",
        "path": "/",
        "expires": 1893456000.0,
        "httpOnly": True,
        "secure": False,
        "sameSite": "Lax",
    }
    assert list(path.parent.iterdir()) == [path]


def test_dev_account_live_board_shows_one_chosen_managers_players(uow, engine):
    from arbit_api.fixture import seed
    from arbit_api.main import create_app
    from arbit_data.members import issue_observer_session

    configured = settings(engine)
    seed(configured, engine)
    token, _ = issue_observer_session(uow)
    app = create_app(configured, engine=engine)
    with TestClient(app, client=("127.0.0.1", 50000)) as member:
        member.post("/auth/fixture", json={"member": "one"}, headers={"Origin": ORIGIN})
        team = member.get("/api/v1/me").json()["teams"][0]["id"]
    put_players_in_the_fictional_game(uow, engine, team)
    with TestClient(app, client=("127.0.0.1", 50000)) as member:
        member.post("/auth/fixture", json={"member": "one"}, headers={"Origin": ORIGIN})
        theirs = member.get("/api/v1/live/games").json()["games"][0]["own_players"]
    assert len(theirs) == 2
    with observer_client(app, token) as client:
        unchosen = client.get("/api/v1/live/games").json()["games"][0]
        assert unchosen["own_players"] == []  # no team of its own until it picks one
        chosen = client.get("/api/v1/live/games", params={"team_id": team}).json()["games"][0]
        assert chosen["own_players"] == theirs
        event = chosen["event_id"]
        detail = client.get(f"/api/v1/live/games/{event}", params={"team_id": team}).json()
        assert detail["game"]["own_players"] == theirs
        plays = client.get(
            f"/api/v1/live/games/{event}/plays", params={"team_id": team, "own": "true"}
        )
        assert plays.status_code == 200
        stranger = "00000000-0000-0000-0000-000000000999"
        refused = client.get("/api/v1/live/games", params={"team_id": stranger})
        assert refused.status_code == 403 and refused.json()["code"] == "TEAM_CONTEXT_DENIED"


def put_players_in_the_fictional_game(uow, engine, team_id):
    """The fictional roster has no NFL teams; give two of one team's players the home team."""
    from arbit_data.live import store as live_store
    from arbit_data.schema import current_snapshot, league_document
    from sqlalchemy import select, update

    home = next(uid for uid, row in live_store.read_directory(uow).items() if row.espn_id == "9901")
    with engine.begin() as c:
        snapshot = c.scalar(
            select(current_snapshot.c.snapshot_id).where(current_snapshot.c.season == 2026)
        )
        payload = c.scalar(
            select(league_document.c.payload).where(league_document.c.snapshot_id == snapshot)
        )
        moved = 0
        for player in payload["players"]:
            if player.get("team_id") == team_id and moved < 2:
                player["nfl_team_id"] = str(home)
                moved += 1
        c.execute(
            update(league_document)
            .where(league_document.c.snapshot_id == snapshot)
            .values(payload=payload)
        )
