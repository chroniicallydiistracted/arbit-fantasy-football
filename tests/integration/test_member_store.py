from datetime import UTC, datetime, timedelta

import pytest


def test_invitations_are_exact_single_use_and_sessions_expire(uow):
    from arbit_data.members import (
        MemberError,
        authenticate,
        create_invitation,
        revoke_sessions,
        sign_in,
    )

    now = datetime.now(UTC)
    invite = create_invitation(uow, "https://identity.example", "one@example.test", now=now)
    for issuer, email, verified in [
        ("https://other.example", "one@example.test", True),
        ("https://identity.example", "two@example.test", True),
        ("https://identity.example", "one@example.test", False),
    ]:
        with pytest.raises(MemberError):
            sign_in(uow, issuer, "subject-one", email, verified, invitation=invite, now=now)
    token, account = sign_in(
        uow,
        "https://identity.example",
        "subject-one",
        "one@example.test",
        True,
        invitation=invite,
        now=now,
    )
    assert authenticate(uow, token, now=now)["id"] == account["id"]
    with pytest.raises(MemberError):
        sign_in(
            uow,
            "https://identity.example",
            "subject-two",
            "one@example.test",
            True,
            invitation=invite,
            now=now,
        )
    assert authenticate(uow, token, now=now + timedelta(days=8)) is None
    token, _ = sign_in(
        uow, "https://identity.example", "subject-one", "one@example.test", True, now=now
    )
    revoke_sessions(uow, account["id"])
    assert authenticate(uow, token, now=now) is None


def test_flows_are_browser_bound_single_use_and_preferences_use_cas(uow):
    from arbit_data.members import (
        MemberError,
        consume_flow,
        create_flow,
        create_invitation,
        sign_in,
        update_preferences,
    )

    flow = create_flow(uow, None)
    with pytest.raises(MemberError):
        consume_flow(uow, flow["state"], "wrong-browser")
    # A wrong-browser attempt does not consume another browser's legitimate flow.
    assert consume_flow(uow, flow["state"], flow["browser"])["nonce"] == flow["nonce"]
    with pytest.raises(MemberError):
        consume_flow(uow, flow["state"], flow["browser"])
    invite = create_invitation(uow, "https://identity.example", "one@example.test")
    _, account = sign_in(
        uow, "https://identity.example", "subject", "one@example.test", True, invitation=invite
    )
    assert update_preferences(uow, account["id"], 0, "dark", [])["version"] == 1
    with pytest.raises(MemberError, match="PREFERENCES_CONFLICT"):
        update_preferences(uow, account["id"], 0, "light", [])


def test_expired_invitation_absolute_session_limit_rotation_and_suspension(uow):
    from arbit_data.members import (
        MemberError,
        authenticate,
        create_invitation,
        revoke_sessions,
        sign_in,
    )

    now = datetime.now(UTC)
    expired = create_invitation(
        uow, "https://identity.example", "one@example.test", now=now - timedelta(days=8)
    )
    with pytest.raises(MemberError):
        sign_in(
            uow,
            "https://identity.example",
            "one",
            "one@example.test",
            True,
            invitation=expired,
            now=now,
        )
    invitation = create_invitation(uow, "https://identity.example", "one@example.test", now=now)
    original, account = sign_in(
        uow,
        "https://identity.example",
        "one",
        "one@example.test",
        True,
        invitation=invitation,
        now=now,
    )
    rotated, _ = sign_in(uow, "https://identity.example", "one", "one@example.test", True, now=now)
    assert authenticate(uow, original, now=now) is None
    for day in range(1, 30):
        assert authenticate(uow, rotated, now=now + timedelta(days=day)) is not None
    assert authenticate(uow, rotated, now=now + timedelta(days=30)) is None
    revoke_sessions(uow, account["id"], suspend=True)
    with pytest.raises(MemberError):
        sign_in(uow, "https://identity.example", "one", "one@example.test", True, now=now)


def test_separate_approved_comanager_accounts_share_only_their_team(uow, engine):
    from uuid import UUID

    from arbit_api.fixture import seed
    from arbit_api.main import create_app
    from arbit_data.members import bind_manager, create_invitation, sign_in
    from fastapi.testclient import TestClient
    from test_member_api import settings

    configured = settings(engine)
    seed(configured, engine)
    invitation = create_invitation(uow, "https://fiction.invalid", "co@fiction.invalid")
    token, account = sign_in(
        uow, "https://fiction.invalid", "co", "co@fiction.invalid", True, invitation=invitation
    )
    bind_manager(uow, account["id"], UUID(int=103), 2026, account["id"])
    token, _ = sign_in(uow, "https://fiction.invalid", "co", "co@fiction.invalid", True)
    app = create_app(configured, engine=engine)
    with TestClient(app, client=("127.0.0.1", 50000)) as browser:
        browser.cookies.set("arbit_session", token)
        me = browser.get("/api/v1/me").json()
        assert len(me["teams"]) == 1
        assert me["teams"][0]["id"] == str(UUID(int=201))
        assert browser.get("/api/v1/front-office").json()["team"]["id"] == str(UUID(int=201))


def test_admin_bootstrap_is_single_outstanding_and_then_permanently_closed(uow):
    from arbit_data.members import MemberError, create_invitation, sign_in

    invitation = create_invitation(
        uow, "https://identity.example", "owner@example.test", role="admin", bootstrap=True
    )
    with pytest.raises(MemberError, match="BOOTSTRAP_CLOSED"):
        create_invitation(
            uow, "https://identity.example", "other@example.test", role="admin", bootstrap=True
        )
    _, account = sign_in(
        uow, "https://identity.example", "owner", "owner@example.test", True, invitation=invitation
    )
    assert account["role"] == "admin"
    with pytest.raises(MemberError, match="BOOTSTRAP_CLOSED"):
        create_invitation(
            uow, "https://identity.example", "other@example.test", role="admin", bootstrap=True
        )


def test_binding_changes_revoke_sessions_atomically_and_prevent_manager_takeover(uow):
    from uuid import UUID

    from arbit_data.members import (
        MemberError,
        authenticate,
        bind_manager,
        create_invitation,
        revoke_binding,
        sign_in,
    )

    tokens = []
    accounts = []
    for name in ["one", "two"]:
        invite = create_invitation(uow, "https://identity.example", f"{name}@example.test")
        token, account = sign_in(
            uow, "https://identity.example", name, f"{name}@example.test", True, invitation=invite
        )
        tokens.append(token)
        accounts.append(account)
    bind_manager(uow, accounts[0]["id"], UUID(int=101), 2026, accounts[0]["id"])
    assert authenticate(uow, tokens[0]) is None
    with pytest.raises(MemberError, match="BINDING_CONFLICT"):
        bind_manager(uow, accounts[1]["id"], UUID(int=101), 2026, accounts[0]["id"])
    revoke_binding(uow, accounts[0]["id"], UUID(int=101), 2026, accounts[0]["id"])
    bind_manager(uow, accounts[1]["id"], UUID(int=101), 2026, accounts[0]["id"])
    assert authenticate(uow, tokens[1]) is None


def test_oidc_flows_are_bounded_expired_pruned_and_secrets_wiped_after_use(uow):
    from arbit_data.member_schema import flow
    from arbit_data.members import MemberError, consume_flow, create_flow, digest
    from sqlalchemy import func, select

    now = datetime.now(UTC)
    expired = create_flow(uow, None, now=now - timedelta(minutes=20))
    active = [create_flow(uow, None, now=now) for _ in range(100)]
    with pytest.raises(MemberError, match="SIGN_IN_LIMIT"):
        create_flow(uow, None, now=now)
    with uow.engine.connect() as c:
        assert c.scalar(select(flow.c.hash).where(flow.c.hash == digest(expired["state"]))) is None
        assert c.scalar(select(func.count()).select_from(flow)) == 100
    captured = consume_flow(uow, active[0]["state"], active[0]["browser"], now=now)
    assert captured["nonce"] == active[0]["nonce"]
    assert captured["verifier"] == active[0]["verifier"]
    with uow.engine.connect() as c:
        persisted = (
            c.execute(select(flow).where(flow.c.hash == digest(active[0]["state"])))
            .mappings()
            .one()
        )
        assert persisted["nonce"] == persisted["verifier"] == persisted["browser_hash"] == ""
        assert persisted["invitation_hash"] is None
    with pytest.raises(MemberError):
        consume_flow(uow, active[0]["state"], active[0]["browser"], now=now)
    create_flow(uow, None, now=now)
    create_flow(uow, None, now=now + timedelta(minutes=11))
    with uow.engine.connect() as c:
        assert c.scalar(select(func.count()).select_from(flow)) == 1


def test_reactivation_is_audited_and_requires_fresh_signin_without_restoring_binding(uow):
    from uuid import UUID

    from arbit_data.member_schema import audit
    from arbit_data.members import (
        MemberError,
        authenticate,
        bind_manager,
        create_invitation,
        manager_ids,
        reactivate_account,
        revoke_binding,
        revoke_sessions,
        sign_in,
    )
    from sqlalchemy import select

    invite = create_invitation(uow, "https://identity.example", "admin@example.test", role="admin")
    _, admin = sign_in(
        uow, "https://identity.example", "admin", "admin@example.test", True, invitation=invite
    )
    invite = create_invitation(uow, "https://identity.example", "member@example.test")
    _, member = sign_in(
        uow, "https://identity.example", "member", "member@example.test", True, invitation=invite
    )
    bind_manager(uow, member["id"], UUID(int=101), 2026, admin["id"])
    token, _ = sign_in(uow, "https://identity.example", "member", "member@example.test", True)
    revoke_binding(uow, member["id"], UUID(int=101), 2026, admin["id"])
    revoke_sessions(uow, member["id"], actor=admin["id"], suspend=True)
    with pytest.raises(MemberError):
        sign_in(uow, "https://identity.example", "member", "member@example.test", True)
    reactivate_account(uow, member["id"], actor=admin["id"])
    assert authenticate(uow, token) is None
    assert manager_ids(uow, member["id"], 2026) == set()
    fresh, _ = sign_in(uow, "https://identity.example", "member", "member@example.test", True)
    assert authenticate(uow, fresh)["id"] == member["id"]
    with uow.engine.connect() as c:
        assert (
            c.scalar(
                select(audit.c.action).where(
                    audit.c.target_id == member["id"], audit.c.action == "account.reactivated"
                )
            )
            == "account.reactivated"
        )


def test_concurrent_suspensions_cannot_remove_last_active_administrator(uow):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from arbit_data.member_schema import account
    from arbit_data.members import MemberError, create_invitation, revoke_sessions, sign_in
    from sqlalchemy import func, select

    admins = []
    for name in ["one", "two"]:
        invite = create_invitation(
            uow, "https://identity.example", f"{name}@example.test", role="admin"
        )
        _, member = sign_in(
            uow, "https://identity.example", name, f"{name}@example.test", True, invitation=invite
        )
        admins.append(member)
    ready = Barrier(2)

    def suspend(member):
        ready.wait(timeout=5)
        try:
            revoke_sessions(uow, member["id"], actor=admins[0]["id"], suspend=True)
            return "suspended"
        except MemberError as error:
            return str(error)

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(suspend, admins))
    assert sorted(outcomes) == ["LAST_ADMINISTRATOR", "suspended"]
    with uow.engine.connect() as c:
        assert (
            c.scalar(
                select(func.count())
                .select_from(account)
                .where(account.c.role == "admin", account.c.suspended.is_(False))
            )
            == 1
        )
