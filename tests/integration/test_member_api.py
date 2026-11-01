from datetime import UTC, datetime
from uuid import UUID

import pytest
from fastapi.testclient import TestClient


def settings(engine, **changes):
    from arbit_api.settings import RuntimeSettings

    return RuntimeSettings(
        environment="test",
        database_url=engine.url.render_as_string(hide_password=False),
        auth_mode="fixture",
        public_origin="http://testserver",
        **changes,
    )


def test_auth_boundary_origin_csrf_and_private_headers(uow, engine):
    from arbit_api.main import create_app

    app = create_app(settings(engine), engine=engine)
    with TestClient(app, client=("127.0.0.1", 50000)) as client:
        assert client.get("/api/v1/me").status_code == 401
        assert (
            client.post(
                "/auth/fixture",
                json={"member": "one"},
                headers={"Origin": "https://attacker.example"},
            ).status_code
            == 403
        )
        login = client.post(
            "/auth/fixture", json={"member": "one"}, headers={"Origin": "http://testserver"}
        )
        assert login.status_code == 200
        assert "HttpOnly" in login.headers["set-cookie"]
        status = client.get("/auth/status").json()
        assert status["authenticated"] is True and status["fixture"] is True
        csrf = status["csrf_token"]
        me = client.get("/api/v1/me")
        assert me.status_code == 200
        assert me.json()["binding_status"] == "pending"
        assert me.headers["cache-control"] == "no-store, private"
        assert (
            client.put(
                "/api/v1/me/preferences", json={"version": 0, "theme": "dark", "watchlist": []}
            ).status_code
            == 403
        )
        headers = {"Origin": "http://testserver", "X-CSRF-Token": csrf}
        assert (
            client.put(
                "/api/v1/me/preferences",
                json={"version": 0, "theme": "dark", "watchlist": []},
                headers=headers,
            ).status_code
            == 200
        )
        assert (
            client.put(
                "/api/v1/me/preferences",
                json={"version": 0, "theme": "light", "watchlist": []},
                headers=headers,
            ).status_code
            == 409
        )
        assert (
            client.post(
                "/api/v1/admin/invitations", json={"email": "other@example.test"}, headers=headers
            ).status_code
            == 403
        )
        assert client.post("/auth/logout", headers=headers).status_code == 200
        assert client.get("/api/v1/me").status_code == 401


def test_fixture_auth_refuses_real_database_and_production():
    from arbit_api.settings import RuntimeSettings
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        RuntimeSettings(
            environment="test",
            auth_mode="fixture",
            public_origin="http://localhost:8000",
            database_url="postgresql+psycopg://u:p@localhost/arbit_local",
        )
    with pytest.raises(ValidationError):
        RuntimeSettings(
            environment="production",
            auth_mode="fixture",
            public_origin="https://example.test",
            database_url="postgresql+psycopg://u:p@localhost/arbit_test",
        )


def test_two_member_team_context_is_server_bound(uow, engine, captured_input):
    import hashlib

    from arbit_api.main import create_app
    from arbit_data.league_store import publish_capture, read_current
    from arbit_data.members import bind_manager

    capture = captured_input.model_copy(deep=True)
    publication = publish_capture(
        capture, hashlib.sha256(capture.model_dump_json().encode()).hexdigest(), uow
    )
    stored = read_current(uow, 2026)
    assert stored
    app = create_app(settings(engine), engine=engine)
    with (
        TestClient(app, client=("127.0.0.1", 50000)) as first,
        TestClient(app, client=("127.0.0.1", 50000)) as second,
    ):
        for client, name in [(first, "one"), (second, "two")]:
            assert (
                client.post(
                    "/auth/fixture", json={"member": name}, headers={"Origin": "http://testserver"}
                ).status_code
                == 200
            )
        me = first.get("/api/v1/me").json()
        bind_manager(
            uow,
            UUID(me["account"]["id"]),
            UUID(stored["league"]["managers"][0]["id"]),
            2026,
            UUID(me["account"]["id"]),
        )
        first.post("/auth/fixture", json={"member": "one"}, headers={"Origin": "http://testserver"})
        home = first.get("/api/v1/front-office")
        assert home.status_code == 200
        assert home.json()["snapshot"]["id"] == str(publication.snapshot_id)
        assert home.json()["team"]["id"] in [
            t["id"] for t in first.get("/api/v1/me").json()["teams"]
        ]
        assert second.get("/api/v1/front-office").status_code == 403
        assert first.get("/api/v1/players/00000000-0000-0000-0000-000000000000").status_code == 404
        assert (
            first.get(
                "/api/v1/front-office?team_id=00000000-0000-0000-0000-000000000000"
            ).status_code
            == 403
        )


def test_browser_callback_is_bound_single_use_and_private(uow, engine, monkeypatch):
    from urllib.parse import parse_qs, urlsplit

    from arbit_api.main import create_app
    from arbit_api.oidc import OidcClient
    from arbit_data.members import create_invitation

    from services.api.tests.test_oidc import provider_settings

    configured = provider_settings().model_copy(
        update={"database_url": settings(engine).database_url, "public_origin": "http://testserver"}
    )
    app = create_app(configured, engine=engine)
    invitation = create_invitation(uow, "https://identity.example", "one@example.test")
    exchanges = []

    def exchange(self, code, flow):
        exchanges.append(code)
        return {
            "sub": "one",
            "email": "one@example.test",
            "email_verified": True,
            "name": "Fictional OIDC test",
        }

    monkeypatch.setattr(OidcClient, "exchange", exchange)
    with (
        TestClient(app, client=("127.0.0.1", 50000)) as browser,
        TestClient(app, client=("127.0.0.1", 50000)) as attacker,
    ):
        start = browser.post(
            "/auth/start", json={"invitation": invitation}, headers={"Origin": "http://testserver"}
        )
        assert start.status_code == 200
        state = parse_qs(urlsplit(start.json()["authorization_url"]).query)["state"][0]
        callback = f"/auth/callback?state={state}&code=private-test-code"
        rejected = attacker.get(callback, follow_redirects=False)
        assert rejected.headers["location"] == "/?auth_error=sign_in_failed"
        assert exchanges == []
        success = browser.get(callback, follow_redirects=False)
        assert success.headers["location"] == "/"
        assert success.headers["cache-control"] == "no-store, private"
        assert "private-test-code" not in success.text
        assert browser.get("/api/v1/me").status_code == 200
        assert (
            browser.get(callback, follow_redirects=False).headers["location"]
            == "/?auth_error=sign_in_failed"
        )
        assert len(exchanges) == 1


def test_synthetic_rehearsal_two_members_history_and_nulls(uow, engine):
    from arbit_api.fixture import seed
    from arbit_api.main import create_app

    configured = settings(engine)
    seed(configured, engine)
    seed(configured, engine)  # explicitly idempotent without replacing another snapshot
    app = create_app(configured, engine=engine)
    with (
        TestClient(app, client=("127.0.0.1", 50000)) as first,
        TestClient(app, client=("127.0.0.1", 50000)) as second,
    ):
        for client, name in [(first, "one"), (second, "two")]:
            assert (
                client.post(
                    "/auth/fixture", json={"member": name}, headers={"Origin": "http://testserver"}
                ).status_code
                == 200
            )
        home = first.get("/api/v1/front-office").json()
        away = second.get("/api/v1/front-office").json()
        assert home["team"]["id"] != away["team"]["id"]
        assert len(home["roster"]) == 12
        assert home["matchup"]["home"]["official_points"] is None
        assert home["roster"][0]["nfl_team_id"] is None
        assert home["roster"][0]["official_current_points"] is None
        assert (
            first.get("/api/v1/front-office", params={"team_id": away["team"]["id"]}).status_code
            == 403
        )
        historical = first.get("/api/v1/front-office?matchup_period=7").json()
        assert historical["historical_roster_unavailable"] is True
        assert historical["roster"] == []
        assert historical["matchup"]["home"]["official_points"] == "128.25"
        player_id = home["roster"][0]["id"]
        pinned = first.get(
            f"/api/v1/players/{player_id}", params={"snapshot_id": home["snapshot"]["id"]}
        )
        assert pinned.json()["snapshot"]["id"] == home["snapshot"]["id"]
        assert (
            first.get(
                f"/api/v1/players/{player_id}?snapshot_id=00000000-0000-0000-0000-000000000000"
            ).status_code
            == 404
        )
        assert first.get("/api/v1/players?query=Juniper").json()["players"]
        assert first.get("/api/v1/players?query=J").status_code == 422


def test_member_readiness_checks_session_tables_not_only_revision(uow, engine):
    from arbit_api.main import create_app
    from sqlalchemy import text

    app = create_app(settings(engine), engine=engine)
    with TestClient(app, client=("127.0.0.1", 50000)) as client:
        assert client.get("/health/ready").status_code == 200
        with engine.begin() as c:
            c.execute(text("DROP TABLE member_flow"))
        assert client.get("/health/ready").status_code == 503


def test_fixture_requests_require_actual_loopback_peer(uow, engine):
    from arbit_api.main import create_app

    app = create_app(settings(engine), engine=engine)
    with TestClient(app, client=("203.0.113.1", 50000)) as remote:
        assert remote.get("/auth/status").status_code == 403
        assert (
            remote.post(
                "/auth/fixture", json={"member": "one"}, headers={"Origin": "http://testserver"}
            ).status_code
            == 403
        )


def test_malformed_csrf_is_safe_forbidden_not_server_error(uow, engine):
    from arbit_api.main import create_app

    app = create_app(settings(engine), engine=engine)
    with TestClient(app, client=("127.0.0.1", 50000)) as client:
        assert (
            client.post(
                "/auth/fixture", json={"member": "one"}, headers={"Origin": "http://testserver"}
            ).status_code
            == 200
        )
        response = client.post(
            "/auth/logout", headers=[(b"origin", b"http://testserver"), (b"x-csrf-token", b"\xff")]
        )
        assert response.status_code == 403
        assert response.json()["error"] == "CSRF_REQUIRED"


def test_invalid_stored_facts_fail_safely_without_echoing_private_input(uow, engine):
    from arbit_api.fixture import seed
    from arbit_api.main import create_app
    from arbit_data.schema import league_document
    from sqlalchemy import update

    configured = settings(engine)
    seed(configured, engine)
    app = create_app(configured, engine=engine)
    with TestClient(app, client=("127.0.0.1", 50000)) as client:
        client.post(
            "/auth/fixture", json={"member": "one"}, headers={"Origin": "http://testserver"}
        )
        with engine.begin() as c:
            c.execute(
                update(league_document).values(
                    payload={"private_input": "do-not-echo-sensitive-data"}
                )
            )
        response = client.get("/api/v1/front-office")
        assert response.status_code == 503
        assert response.json()["error"] == "MEMBER_FACTS_UNAVAILABLE"
        assert "do-not-echo-sensitive-data" not in response.text


def test_unbound_accounts_cannot_read_league_or_change_watchlist(uow, engine):
    from uuid import UUID

    from arbit_api.fixture import seed
    from arbit_api.main import create_app
    from arbit_data.members import create_invitation, sign_in, update_preferences

    configured = settings(engine)
    seed(configured, engine)
    invitation = create_invitation(uow, "https://fiction.invalid", "pending@fiction.invalid")
    token, account = sign_in(
        uow,
        "https://fiction.invalid",
        "pending",
        "pending@fiction.invalid",
        True,
        invitation=invitation,
    )
    app = create_app(configured, engine=engine)
    with TestClient(app, client=("127.0.0.1", 50000)) as client:
        client.cookies.set("arbit_session", token)
        assert client.get("/api/v1/me").json()["binding_status"] == "pending"
        for path in [
            "/api/v1/league/teams",
            "/api/v1/players?query=Juniper",
            f"/api/v1/players/{UUID(int=21100)}",
        ]:
            response = client.get(path)
            assert response.status_code == 403
            assert response.json()["error"] == "BINDING_REQUIRED"
        headers = {
            "Origin": "http://testserver",
            "X-CSRF-Token": client.get("/auth/status").json()["csrf_token"],
        }
        assert (
            client.put(
                "/api/v1/me/preferences",
                json={"version": 0, "theme": "dark", "watchlist": []},
                headers=headers,
            ).status_code
            == 200
        )
        assert (
            client.put(
                "/api/v1/me/preferences",
                json={"version": 1, "theme": "dark", "watchlist": [str(UUID(int=21100))]},
                headers=headers,
            ).status_code
            == 403
        )
        update_preferences(uow, account["id"], 1, "dark", [UUID(int=21100)])
        # Existing watchlist does not prevent a theme-only change, but clearing it remains a change.
        assert (
            client.put(
                "/api/v1/me/preferences",
                json={"version": 2, "theme": "light", "watchlist": [str(UUID(int=21100))]},
                headers=headers,
            ).status_code
            == 200
        )
        assert (
            client.put(
                "/api/v1/me/preferences",
                json={"version": 3, "theme": "light", "watchlist": []},
                headers=headers,
            ).status_code
            == 403
        )


def test_front_office_orders_standings_by_reported_seed_and_reports_freshness(uow, engine):
    from datetime import UTC, datetime

    from arbit_api.fixture import seed
    from arbit_api.main import create_app
    from arbit_data.schema import league_document, sync_state
    from sqlalchemy import select, update

    configured = settings(engine)
    seed(configured, engine)
    with engine.begin() as c:
        document = c.scalar(select(league_document.c.payload))
        document["teams"].reverse()
        c.execute(update(league_document).values(payload=document))
        c.execute(update(sync_state).values(paused=False, last_success_at=datetime.now(UTC)))
    app = create_app(configured, engine=engine)
    with TestClient(app, client=("127.0.0.1", 50000)) as client:
        client.post(
            "/auth/fixture", json={"member": "one"}, headers={"Origin": "http://testserver"}
        )
        response = client.get("/api/v1/front-office").json()
        seeds = [t["playoff_seed"] for t in response["standings"]]
        assert seeds == sorted(seeds), "provider order must not leak into the league table"
        assert [t["id"] for t in response["standings"]] != [t["id"] for t in document["teams"]]
        assert response["snapshot"]["source_status"] == "fresh"
        assert response["snapshot"]["stale"] is False
        with engine.begin() as c:
            c.execute(update(sync_state).values(paused=True))
        assert client.get("/api/v1/front-office").json()["snapshot"]["source_status"] == "degraded"


def test_admin_invitation_uses_join_fragment_route(uow, engine):
    from urllib.parse import urlsplit

    from arbit_api.main import create_app
    from arbit_data.members import create_invitation, sign_in

    from services.api.tests.test_oidc import provider_settings

    configured = provider_settings().model_copy(
        update={"database_url": settings(engine).database_url, "public_origin": "http://testserver"}
    )
    invite = create_invitation(
        uow, "https://identity.example", "admin@example.test", role="admin", bootstrap=True
    )
    token, _ = sign_in(
        uow, "https://identity.example", "admin", "admin@example.test", True, invitation=invite
    )
    with TestClient(create_app(configured, engine=engine)) as client:
        client.cookies.set("arbit_session", token)
        headers = {
            "Origin": "http://testserver",
            "X-CSRF-Token": client.get("/auth/status").json()["csrf_token"],
        }
        response = client.post(
            "/api/v1/admin/invitations", json={"email": "member@example.test"}, headers=headers
        )
        assert response.status_code == 200
        link = urlsplit(response.json()["invitation_url"])
        assert link.path == "/join"
        assert len(link.fragment) >= 32 and "=" not in link.fragment
        assert link.query == ""


def test_auth_flow_limit_returns_safe_retry_after(uow, engine):
    from arbit_api.main import create_app
    from arbit_data.members import create_flow

    from services.api.tests.test_oidc import provider_settings

    configured = provider_settings().model_copy(
        update={"database_url": settings(engine).database_url, "public_origin": "http://testserver"}
    )
    for _ in range(100):
        create_flow(uow, None)
    with TestClient(create_app(configured, engine=engine)) as client:
        response = client.post("/auth/start", json={}, headers={"Origin": "http://testserver"})
        assert response.status_code == 429
        assert response.headers["retry-after"] == "600"
        assert response.json()["error"] == "SIGN_IN_LIMIT"
        assert response.headers["cache-control"] == "no-store, private"


def test_admin_directory_lists_only_active_bindings_for_configured_season(uow, engine):
    from uuid import UUID

    from arbit_api.fixture import seed
    from arbit_api.main import create_app
    from arbit_data.members import bind_manager, create_invitation, revoke_binding, sign_in

    from services.api.tests.test_oidc import provider_settings

    configured = provider_settings().model_copy(
        update={"database_url": settings(engine).database_url, "public_origin": "http://testserver"}
    )
    seed(settings(engine), engine)
    invite = create_invitation(
        uow, "https://identity.example", "admin@example.test", role="admin", bootstrap=True
    )
    token, admin = sign_in(
        uow, "https://identity.example", "admin", "admin@example.test", True, invitation=invite
    )
    with TestClient(create_app(configured, engine=engine)) as client:
        client.cookies.set("arbit_session", token)
        directory = client.get("/api/v1/admin/directory")
        assert directory.status_code == 200
        member = next(
            a for a in directory.json()["accounts"] if a["display_name"] == "Fictional member one"
        )
        assert member["manager_ids"] == [str(UUID(int=101))]
        bind_manager(uow, UUID(member["id"]), UUID(int=999), 2027, admin["id"])
        member = next(
            a
            for a in client.get("/api/v1/admin/directory").json()["accounts"]
            if a["id"] == member["id"]
        )
        assert member["manager_ids"] == [str(UUID(int=101))]
        revoke_binding(uow, UUID(member["id"]), UUID(int=101), 2026, admin["id"])
        member = next(
            a
            for a in client.get("/api/v1/admin/directory").json()["accounts"]
            if a["id"] == member["id"]
        )
        assert member["manager_ids"] == []


def test_admin_reactivation_endpoint_and_last_admin_guard(uow, engine):
    from arbit_api.main import create_app
    from arbit_data.members import authenticate, create_invitation, revoke_sessions, sign_in

    from services.api.tests.test_oidc import provider_settings

    configured = provider_settings().model_copy(
        update={"database_url": settings(engine).database_url, "public_origin": "http://testserver"}
    )
    invite = create_invitation(uow, "https://identity.example", "admin@example.test", role="admin")
    admin_token, admin = sign_in(
        uow, "https://identity.example", "admin", "admin@example.test", True, invitation=invite
    )
    invite = create_invitation(uow, "https://identity.example", "member@example.test")
    member_token, member = sign_in(
        uow, "https://identity.example", "member", "member@example.test", True, invitation=invite
    )
    revoke_sessions(uow, member["id"], actor=admin["id"], suspend=True)
    with TestClient(create_app(configured, engine=engine)) as client:
        client.cookies.set("arbit_session", admin_token)
        headers = {
            "Origin": "http://testserver",
            "X-CSRF-Token": client.get("/auth/status").json()["csrf_token"],
        }
        response = client.post(
            "/api/v1/admin/sessions/revoke",
            json={"account_id": str(admin["id"]), "suspend": True},
            headers=headers,
        )
        assert response.status_code == 409
        assert response.json()["error"] == "LAST_ADMINISTRATOR"
        response = client.post(
            "/api/v1/admin/accounts/reactivate",
            json={"account_id": str(member["id"])},
            headers=headers,
        )
        assert response.status_code == 200
        assert authenticate(uow, member_token) is None
        fresh, _ = sign_in(uow, "https://identity.example", "member", "member@example.test", True)
        assert authenticate(uow, fresh) is not None
        client.cookies.set("arbit_session", fresh)
        member_headers = {
            "Origin": "http://testserver",
            "X-CSRF-Token": client.get("/auth/status").json()["csrf_token"],
        }
        assert (
            client.post(
                "/api/v1/admin/accounts/reactivate",
                json={"account_id": str(member["id"])},
                headers=member_headers,
            ).status_code
            == 403
        )


def test_member_errors_are_private_typed_problems_with_safe_request_ids(uow, engine):
    import re

    from arbit_api.fixture import seed
    from arbit_api.main import create_app
    from arbit_data.schema import league_document
    from sqlalchemy import update

    configured = settings(engine)
    seed(configured, engine)
    app = create_app(configured, engine=engine)
    with TestClient(app, client=("127.0.0.1", 50000)) as client:
        client.post(
            "/auth/fixture", json={"member": "one"}, headers={"Origin": "http://testserver"}
        )
        responses = [
            client.post(
                "/auth/logout",
                headers={
                    "Origin": "https://attacker.example",
                    "X-Request-ID": "private-input-do-not-echo",
                },
            )
        ]
        responses.append(
            client.put(
                "/api/v1/me/preferences",
                json={"version": 0, "theme": "private-input-do-not-echo", "watchlist": []},
                headers={
                    "Origin": "http://testserver",
                    "X-CSRF-Token": client.get("/auth/status").json()["csrf_token"],
                },
            )
        )
        with engine.begin() as c:
            c.execute(update(league_document).values(payload={"private-input-do-not-echo": True}))
        responses.append(client.get("/api/v1/front-office"))
        ids = set()
        for response, status, code in zip(
            responses,
            [403, 422, 503],
            ["ORIGIN_REQUIRED", "INVALID_REQUEST", "MEMBER_FACTS_UNAVAILABLE"],
            strict=True,
        ):
            assert response.status_code == status
            assert response.headers["content-type"].startswith("application/problem+json")
            problem = response.json()
            assert problem["status"] == status
            assert problem["code"] == problem["error"] == code
            assert problem["type"] == f"urn:arbit:problem:{code}"
            assert problem["title"] and problem["detail"]
            assert re.fullmatch("[a-f0-9]{32}", problem["requestId"])
            assert response.headers["x-request-id"] == problem["requestId"]
            assert problem["instance"] == f"urn:arbit:request:{problem['requestId']}"
            assert response.headers["cache-control"] == "no-store, private"
            assert "private-input-do-not-echo" not in response.text
            ids.add(problem["requestId"])
        assert len(ids) == 3
        health = client.get("/health/live")
        assert health.json() == {"status": "alive"}
        assert health.headers["content-type"].startswith("application/json")
        assert "x-request-id" not in health.headers
    schema = app.openapi()
    for path in ["/api/v1/me", "/api/v1/me/preferences", "/auth/start"]:
        for operation in schema["paths"][path].values():
            for status in ["401", "403", "404", "409", "422", "429", "503"]:
                content = operation["responses"][status]["content"]
                assert set(content) == {"application/problem+json"}
                assert (
                    content["application/problem+json"]["schema"]["$ref"]
                    == "#/components/schemas/Problem"
                )


def test_repeated_fictional_login_and_reseed_preserve_invites_without_accumulation(uow, engine):
    from datetime import UTC, datetime

    from arbit_api.fixture import seed
    from arbit_api.main import create_app
    from arbit_data.member_schema import invitation
    from arbit_data.members import create_invitation
    from sqlalchemy import func, select

    configured = settings(engine)
    # Preserve a pre-existing unredeemed record; repeated preview use must not clean it up.
    create_invitation(uow, "https://fiction.invalid", "existing-private-invitation@fiction.invalid")
    seed(configured, engine)

    def inventory():
        with engine.connect() as c:
            hashes = set(c.scalars(select(invitation.c.hash)))
            active = c.scalar(
                select(func.count())
                .select_from(invitation)
                .where(
                    invitation.c.redeemed_at.is_(None), invitation.c.expires_at > datetime.now(UTC)
                )
            )
            return hashes, active

    before = inventory()
    assert before[1] == 1
    with TestClient(create_app(configured, engine=engine), client=("127.0.0.1", 50000)) as client:
        for name in ["one", "two", "one"]:
            assert (
                client.post(
                    "/auth/fixture", json={"member": name}, headers={"Origin": "http://testserver"}
                ).status_code
                == 200
            )
            seed(configured, engine)
    assert inventory() == before


def test_admin_manager_options_include_verified_first_name_and_team_context(
    uow, engine, tmp_path, captured_input
):
    from dataclasses import replace

    from arbit_api.main import create_app
    from arbit_data.archives import CaptureArchive
    from arbit_data.league_store import publish_capture
    from arbit_data.members import create_invitation, sign_in

    from services.api.tests.test_oidc import provider_settings

    acquisition = captured_input.acquisition
    original = acquisition.league.members[0]
    member = original.model_copy(update={"display_name": "ESPNFAN001", "first_name": "Avery"})
    capture = captured_input.model_copy(
        update={
            "acquisition": replace(
                acquisition, league=acquisition.league.model_copy(update={"members": (member,)})
            )
        }
    )
    digest = CaptureArchive(tmp_path).write(capture)
    publish_capture(capture, digest, uow, now=acquisition.capture_finished_at)
    configured = provider_settings().model_copy(
        update={"database_url": settings(engine).database_url, "public_origin": "http://testserver"}
    )
    invitation = create_invitation(
        uow, "https://identity.example", "admin@example.test", role="admin", bootstrap=True
    )
    token, _ = sign_in(
        uow, "https://identity.example", "admin", "admin@example.test", True, invitation=invitation
    )
    with TestClient(create_app(configured, engine=engine)) as client:
        client.cookies.set("arbit_session", token)
        result = client.get("/api/v1/admin/directory")
        assert result.status_code == 200
        manager = result.json()["managers"][0]
        assert manager["first_name"] == "Avery"
        assert manager["display_name"] == "ESPNFAN001"
        assert manager["team_names"]
        assert len(manager["team_names"]) == len(manager["team_ids"])


def test_front_office_season_strip_and_roster_order_come_from_stored_facts(uow, engine):
    from arbit_api.fixture import seed
    from arbit_api.main import create_app
    from arbit_data.schema import league_document
    from sqlalchemy import select, update

    configured = settings(engine)
    seed(configured, engine)
    with engine.begin() as c:
        document = c.scalar(select(league_document.c.payload))
        document["players"].reverse()
        c.execute(update(league_document).values(payload=document))
    app = create_app(configured, engine=engine)
    with TestClient(app, client=("127.0.0.1", 50000)) as client:
        client.post(
            "/auth/fixture", json={"member": "one"}, headers={"Origin": "http://testserver"}
        )
        office = client.get("/api/v1/front-office").json()
        slots = [p["lineup_slot"] for p in office["roster"]]
        assert slots[0] == "QB" and slots[-1] == "IR"
        assert slots.index("BENCH") > slots.index("K"), "bench follows every starter"
        strip = {cell["matchup_period"]: cell for cell in office["season_strip"]}
        assert strip[7]["result"] == "win", "a completed period reports its result"
        assert strip[8]["result"] is None, "the current period has no result, even with totals"
        assert office["playoff_team_count"] is None, "an absent rule stays unknown, not a default"


def test_official_totals_never_show_provider_float_noise(uow, engine):
    """Observed in real ESPN data: season points_for of 899.3000000000001."""
    from arbit_api.fixture import seed
    from arbit_api.main import create_app
    from arbit_data.schema import league_document
    from sqlalchemy import select, update

    configured = settings(engine)
    seed(configured, engine)
    with engine.begin() as c:
        document = c.scalar(select(league_document.c.payload))
        for team in document["teams"]:
            team["points_for"] = "899.3000000000001"
        c.execute(update(league_document).values(payload=document))
    with TestClient(create_app(configured, engine=engine), client=("127.0.0.1", 50000)) as client:
        client.post(
            "/auth/fixture", json={"member": "one"}, headers={"Origin": "http://testserver"}
        )
        office = client.get("/api/v1/front-office").json()
    assert {t["points_for"] for t in office["standings"]} == {"899.30"}
    assert office["team"]["points_for"] == "899.30"


def test_unplayed_games_report_no_score_and_a_member_needs_a_team_for_live_data(uow, engine):
    """ESPN sends 0 before kickoff. Unknown is not zero."""
    from arbit_api.fixture import fixture_game, seed
    from arbit_api.main import create_app
    from arbit_data.live import store

    configured = settings(engine)
    seed(configured, engine)
    store.publish_scoreboard(
        uow,
        {"season": 2026, "season_type": 2, "week": 8, "games": [fixture_game("0", "scheduled")]},
        datetime.now(UTC),
    )
    with TestClient(create_app(configured, engine=engine), client=("127.0.0.1", 50000)) as client:
        assert client.get("/api/v1/live/games").status_code == 401
        client.post(
            "/auth/fixture", json={"member": "one"}, headers={"Origin": "http://testserver"}
        )
        game = client.get("/api/v1/live/games").json()["games"][0]
        assert game["home"]["score"] is None and game["away"]["score"] is None
        assert game["home"]["abbreviation"] == "FIC"
        assert client.get("/api/v1/live/games/1/plays").status_code == 404
        assert client.get("/api/v1/live/games/not-a-game/plays").status_code == 422


def test_live_scoreboard_states_the_situation_only_while_a_game_is_on(uow, engine):
    from arbit_api.fixture import fixture_game, seed
    from arbit_api.main import create_app
    from arbit_data.live import store

    configured = settings(engine)
    seed(configured, engine)
    with TestClient(create_app(configured, engine=engine), client=("127.0.0.1", 50000)) as client:
        client.post(
            "/auth/fixture", json={"member": "one"}, headers={"Origin": "http://testserver"}
        )
        live = client.get("/api/v1/live/games/990000001").json()
        situation = live["game"]["situation"]
        assert situation["short_text"] == "3rd & 7"
        assert situation["possession"] == "home"
        # Home drives away from its own goal line, which is 0 on ESPN's scale.
        assert situation["first_down_line"] == 45
        assert (
            live["game"]["home"]["has_ball"] is True and live["game"]["away"]["has_ball"] is False
        )
        assert live["game"]["home"]["timeouts"] == 3
        assert [d["current"] for d in live["drives"]] == [False, True]
        assert live["team_stats"][0] == {
            "key": "totalYards",
            "label": "Total Yards",
            "home": "121",
            "away": "96",
        }
        assert live["leaders"][0]["team"] == "FIC"
        assert client.get("/api/v1/live/games/1").status_code == 404
        assert client.get("/api/v1/live/games/not-a-game").status_code == 422

        store.publish_scoreboard(
            uow,
            {"season": 2026, "season_type": 2, "week": 8, "games": [fixture_game("9", "final")]},
            datetime.now(UTC),
        )
        ended = client.get("/api/v1/live/games/990000001").json()["game"]
        assert ended["situation"] is None
        assert ended["home"]["has_ball"] is False and ended["home"]["timeouts"] is None
        assert ended["home"]["score"] == "9", "the final score stays"

        halftime = fixture_game("9", "halftime")
        store.publish_scoreboard(
            uow,
            {"season": 2026, "season_type": 2, "week": 8, "games": [halftime]},
            datetime.now(UTC),
        )
        assert client.get("/api/v1/live/games/990000001").json()["game"]["situation"] is None


def test_away_team_first_down_line_runs_toward_the_home_goal(uow, engine):
    from arbit_api.fixture import FIXTURE_AWAY, fixture_game, seed
    from arbit_api.main import create_app
    from arbit_data.live import store

    configured = settings(engine)
    seed(configured, engine)
    game = fixture_game("7")
    # Goal to go from the 8: the line to gain is the goal line itself, never past it.
    game["situation"] = {
        "distance": 8,
        "yard_line": 8,
        "possession_team_id": FIXTURE_AWAY,
        "red_zone": True,
    }
    store.publish_scoreboard(
        uow, {"season": 2026, "season_type": 2, "week": 8, "games": [game]}, datetime.now(UTC)
    )
    with TestClient(create_app(configured, engine=engine), client=("127.0.0.1", 50000)) as client:
        client.post(
            "/auth/fixture", json={"member": "one"}, headers={"Origin": "http://testserver"}
        )
        situation = client.get("/api/v1/live/games").json()["games"][0]["situation"]
        assert situation["possession"] == "away" and situation["first_down_line"] == 0
        assert situation["red_zone"] is None, "ESPN's flag alone, with no down, is stale"


def test_sources_hide_provider_codes_from_members(uow, engine):
    from arbit_api.fixture import seed
    from arbit_api.main import create_app
    from arbit_data import freshness

    configured = settings(engine)
    seed(configured, engine)
    freshness.record_failure(
        uow,
        freshness.SCOREBOARD,
        "RATE_LIMITED",
        now=datetime.now(UTC),
        cadence_seconds=15,
        stale_after_seconds=60,
    )
    with TestClient(create_app(configured, engine=engine), client=("127.0.0.1", 50000)) as client:
        client.post(
            "/auth/fixture", json={"member": "one"}, headers={"Origin": "http://testserver"}
        )
        rows = client.get("/api/v1/sources").json()["sources"]
    assert [r["source"] for r in rows][:2] == ["espn.league", "espn.nfl.scoreboard"]
    assert all(r["error_code"] is None for r in rows)


def test_device_sessions_require_csrf_and_stay_with_their_owner(uow, engine):
    from arbit_api.fixture import seed
    from arbit_api.main import create_app

    configured = settings(engine)
    seed(configured, engine)
    app = create_app(configured, engine=engine)
    origin = {"Origin": "http://testserver"}
    with (
        TestClient(app, client=("127.0.0.1", 50000)) as one,
        TestClient(app, client=("127.0.0.1", 50000)) as two,
    ):
        one.post("/auth/fixture", json={"member": "one"}, headers=origin)
        two.post("/auth/fixture", json={"member": "two"}, headers=origin)
        session_id = one.get("/api/v1/me/sessions").json()["sessions"][0]["id"]
        assert one.get("/api/v1/me/sessions").json()["sessions"][0]["current"] is True
        body = {"session_id": session_id}
        assert one.post("/api/v1/me/sessions/revoke", json=body, headers=origin).status_code == 403
        csrf = {**origin, "X-CSRF-Token": two.get("/auth/status").json()["csrf_token"]}
        denied = two.post("/api/v1/me/sessions/revoke", json=body, headers=csrf)
        assert denied.status_code == 403 and denied.json()["code"] == "SESSION_NOT_FOUND"
        assert one.get("/api/v1/me").status_code == 200, "another member can't end this session"
