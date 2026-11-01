"""Transactional invite-only accounts, browser flows and opaque member sessions.

Provider identity is issuer+subject. Email can redeem a private invitation but never
reassigns an existing account or grants a fantasy manager binding.
"""

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import and_, delete, func, insert, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from arbit_data.db import UnitOfWork
from arbit_data.member_schema import account, audit, binding, flow, preferences, session
from arbit_data.member_schema import invitation as invitation_table

# A session survives a month without use and three months in total. Privilege changes still
# end every session at once.
SESSION_IDLE = timedelta(days=30)
SESSION_ABSOLUTE = timedelta(days=90)
# Oldest sessions beyond this are ended when a new device signs in.
MAX_DEVICES = 10


class MemberError(ValueError):
    """Safe stable boundary code, never a raw provider or SQL error."""


def digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def csrf_token(token: str) -> str:
    return digest("arbit-csrf-v1:" + token)


def create_invitation(
    uow: UnitOfWork,
    issuer: str,
    email: str,
    *,
    role: str = "member",
    bootstrap: bool = False,
    actor: UUID | None = None,
    now: datetime | None = None,
) -> str:
    if role not in ("member", "admin") or not 3 <= len(email) <= 320 or "@" not in email:
        raise MemberError("INVALID_INVITATION")
    token = secrets.token_urlsafe(32)
    now = now or datetime.now(UTC)
    with uow.engine.begin() as c:
        c.execute(select(func.pg_advisory_xact_lock(1729878439, 0)))
        if bootstrap and (
            role != "admin"
            or c.scalar(select(account.c.id).where(account.c.role == "admin").limit(1)) is not None
            or c.scalar(
                select(invitation_table.c.hash)
                .where(
                    invitation_table.c.role == "admin",
                    invitation_table.c.redeemed_at.is_(None),
                    invitation_table.c.expires_at > now,
                )
                .limit(1)
            )
            is not None
        ):
            raise MemberError("BOOTSTRAP_CLOSED")
        if (
            c.scalar(
                select(func.count())
                .select_from(invitation_table)
                .where(
                    invitation_table.c.redeemed_at.is_(None), invitation_table.c.expires_at > now
                )
            )
            or 0
        ) >= 100:
            raise MemberError("INVITATION_LIMIT")
        c.execute(
            insert(invitation_table).values(
                hash=digest(token),
                issuer=issuer,
                email=email.strip().casefold(),
                role=role,
                expires_at=now + timedelta(days=7),
                created_by=actor,
            )
        )
        c.execute(
            insert(audit).values(actor_id=actor, action="invitation.created", occurred_at=now)
        )
    return token


def account_exists(uow: UnitOfWork, issuer: str, subject: str) -> bool:
    """Exact provider identity lookup; email/name never establishes account identity."""
    with uow.engine.connect() as c:
        return (
            c.scalar(
                select(account.c.id).where(account.c.issuer == issuer, account.c.subject == subject)
            )
            is not None
        )


def sign_in(
    uow: UnitOfWork,
    issuer: str,
    subject: str,
    email: str,
    verified: bool,
    *,
    invitation: str | None = None,
    invitation_hash: str | None = None,
    display_name: str = "FFA member",
    replaces: str | None = None,
    device_label: str | None = None,
    now: datetime | None = None,
) -> tuple[str, dict[str, Any]]:
    now = now or datetime.now(UTC)
    if not verified or not subject or len(subject) > 255 or not 3 <= len(email) <= 320:
        raise MemberError("SIGN_IN_DENIED")
    with uow.engine.begin() as c:
        # Serialize same-identity first logins as well as invitation consumption.
        c.execute(select(func.pg_advisory_xact_lock(int(digest(issuer + "\0" + subject)[:15], 16))))
        row = (
            c.execute(
                select(account)
                .where(account.c.issuer == issuer, account.c.subject == subject)
                .with_for_update()
            )
            .mappings()
            .first()
        )
        if row is None:
            key = digest(invitation) if invitation else invitation_hash
            invite = (
                c.execute(
                    select(invitation_table).where(invitation_table.c.hash == key).with_for_update()
                )
                .mappings()
                .first()
                if key
                else None
            )
            if (
                not invite
                or invite["redeemed_at"] is not None
                or invite["expires_at"] <= now
                or invite["issuer"] != issuer
                or not hmac.compare_digest(
                    invite["email"].encode(), email.strip().casefold().encode()
                )
            ):
                raise MemberError("INVITATION_REQUIRED")
            account_id = uuid4()
            name = (
                "".join(ch for ch in display_name if ch.isprintable()).strip()[:100] or "FFA member"
            )
            c.execute(
                insert(account).values(
                    id=account_id,
                    issuer=issuer,
                    subject=subject,
                    display_name=name,
                    role=invite["role"],
                    suspended=False,
                    created_at=now,
                )
            )
            c.execute(
                update(invitation_table)
                .where(invitation_table.c.hash == key)
                .values(redeemed_at=now)
            )
            c.execute(
                insert(preferences).values(
                    account_id=account_id, version=0, theme="system", watchlist=[]
                )
            )
            row = c.execute(select(account).where(account.c.id == account_id)).mappings().one()
        if row["suspended"]:
            raise MemberError("SIGN_IN_DENIED")
        # Replace the session this browser presented, whoever it belonged to, so a new sign-in
        # always gets a new secret. Other devices stay signed in.
        if replaces:
            c.execute(
                update(session)
                .where(session.c.hash == digest(replaces), session.c.revoked_at.is_(None))
                .values(revoked_at=now)
            )
        stale: list[str] = list(
            c.scalars(
                select(session.c.hash)
                .where(
                    session.c.account_id == row["id"],
                    session.c.revoked_at.is_(None),
                    session.c.expires_at > now,
                )
                .order_by(session.c.last_seen_at.desc())
                .offset(MAX_DEVICES - 1)
            )
        )
        if stale:
            c.execute(update(session).where(session.c.hash.in_(stale)).values(revoked_at=now))
        token = secrets.token_urlsafe(32)
        c.execute(
            insert(session).values(
                hash=digest(token),
                account_id=row["id"],
                created_at=now,
                last_seen_at=now,
                expires_at=now + SESSION_ABSOLUTE,
                device_label=(device_label or "")[:80] or None,
            )
        )
        c.execute(
            insert(audit).values(target_id=row["id"], action="session.created", occurred_at=now)
        )
        return token, dict(row)


def authenticate(
    uow: UnitOfWork, token: str, *, now: datetime | None = None
) -> dict[str, Any] | None:
    if not 32 <= len(token) <= 128:
        return None
    now = now or datetime.now(UTC)
    with uow.engine.begin() as c:
        row = (
            c.execute(
                select(account)
                .join(session, session.c.account_id == account.c.id)
                .where(
                    session.c.hash == digest(token),
                    session.c.revoked_at.is_(None),
                    session.c.expires_at > now,
                    session.c.last_seen_at > now - SESSION_IDLE,
                    account.c.suspended.is_(False),
                )
                .with_for_update()
            )
            .mappings()
            .first()
        )
        if row is None:
            return None
        c.execute(update(session).where(session.c.hash == digest(token)).values(last_seen_at=now))
        return dict(row)


def revoke_sessions(
    uow: UnitOfWork, account_id: UUID, *, actor: UUID | None = None, suspend: bool = False
) -> None:
    now = datetime.now(UTC)
    with uow.engine.begin() as c:
        # Serialize all administrator suspension/reactivation decisions before row locks.
        if suspend:
            c.execute(select(func.pg_advisory_xact_lock(1729878439, 2)))
        target = (
            c.execute(select(account).where(account.c.id == account_id).with_for_update())
            .mappings()
            .first()
        )
        if target is None:
            raise MemberError("ACCOUNT_NOT_FOUND")
        if suspend and target["role"] == "admin" and not target["suspended"]:
            active = (
                c.scalar(
                    select(func.count())
                    .select_from(account)
                    .where(account.c.role == "admin", account.c.suspended.is_(False))
                )
                or 0
            )
            if active <= 1:
                raise MemberError("LAST_ADMINISTRATOR")
        c.execute(
            update(session)
            .where(session.c.account_id == account_id, session.c.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        if suspend:
            c.execute(update(account).where(account.c.id == account_id).values(suspended=True))
        c.execute(
            insert(audit).values(
                actor_id=actor,
                target_id=account_id,
                action="account.suspended" if suspend else "sessions.revoked",
                occurred_at=now,
            )
        )


def reactivate_account(uow: UnitOfWork, account_id: UUID, *, actor: UUID) -> None:
    now = datetime.now(UTC)
    with uow.engine.begin() as c:
        c.execute(select(func.pg_advisory_xact_lock(1729878439, 2)))
        if (
            c.scalar(select(account.c.id).where(account.c.id == account_id).with_for_update())
            is None
        ):
            raise MemberError("ACCOUNT_NOT_FOUND")
        c.execute(update(account).where(account.c.id == account_id).values(suspended=False))
        # Deliberately leave session and manager-binding revocations untouched.
        c.execute(
            insert(audit).values(
                actor_id=actor, target_id=account_id, action="account.reactivated", occurred_at=now
            )
        )


def logout(uow: UnitOfWork, token: str) -> None:
    with uow.engine.begin() as c:
        c.execute(
            update(session)
            .where(session.c.hash == digest(token))
            .values(revoked_at=datetime.now(UTC))
        )


def list_sessions(
    uow: UnitOfWork, account_id: UUID, current_token: str, *, now: datetime | None = None
) -> list[dict[str, Any]]:
    """The member's signed-in devices. Exposes the public ID only, never a session secret."""
    now = now or datetime.now(UTC)
    current = digest(current_token)
    with uow.engine.connect() as c:
        rows = c.execute(
            select(session)
            .where(
                session.c.account_id == account_id,
                session.c.revoked_at.is_(None),
                session.c.expires_at > now,
                session.c.last_seen_at > now - SESSION_IDLE,
            )
            .order_by(session.c.last_seen_at.desc())
        ).all()
    return [
        {
            "id": r.public_id,
            "device": r.device_label,
            "created_at": r.created_at,
            "last_seen_at": r.last_seen_at,
            "current": r.hash == current,
        }
        for r in rows
    ]


def revoke_device(uow: UnitOfWork, account_id: UUID, public_id: UUID) -> None:
    """End one of the member's own sessions. Another member's ID behaves as not found."""
    now = datetime.now(UTC)
    with uow.engine.begin() as c:
        ended = c.execute(
            update(session)
            .where(
                session.c.public_id == public_id,
                session.c.account_id == account_id,
                session.c.revoked_at.is_(None),
            )
            .values(revoked_at=now)
        ).rowcount
        if not ended:
            raise MemberError("SESSION_NOT_FOUND")
        c.execute(
            insert(audit).values(
                actor_id=account_id, target_id=account_id, action="session.revoked", occurred_at=now
            )
        )


def create_flow(
    uow: UnitOfWork, invite: str | None, *, now: datetime | None = None
) -> dict[str, str]:
    now = now or datetime.now(UTC)
    values = {k: secrets.token_urlsafe(32) for k in ("state", "browser", "nonce", "verifier")}
    limited = False
    with uow.engine.begin() as c:
        c.execute(select(func.pg_advisory_xact_lock(1729878439, 1)))
        c.execute(
            delete(flow).where(or_(flow.c.expires_at <= now, flow.c.consumed_at.is_not(None)))
        )
        active = (
            c.scalar(
                select(func.count())
                .select_from(flow)
                .where(flow.c.consumed_at.is_(None), flow.c.expires_at > now)
            )
            or 0
        )
        limited = active >= 100
        if not limited:
            c.execute(
                insert(flow).values(
                    hash=digest(values["state"]),
                    browser_hash=digest(values["browser"]),
                    nonce=values["nonce"],
                    verifier=values["verifier"],
                    invitation_hash=digest(invite) if invite else None,
                    expires_at=now + timedelta(minutes=10),
                )
            )
    # Commit pruning even when the active-flow limit refuses a new sign-in.
    if limited:
        raise MemberError("SIGN_IN_LIMIT")
    return values


def consume_flow(
    uow: UnitOfWork, state: str, browser: str, *, now: datetime | None = None
) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    if not 32 <= len(state) <= 128 or not 32 <= len(browser) <= 128:
        raise MemberError("SIGN_IN_FAILED")
    with uow.engine.begin() as c:
        row = (
            c.execute(
                select(flow)
                .where(
                    flow.c.hash == digest(state),
                    flow.c.browser_hash == digest(browser),
                    flow.c.expires_at > now,
                    flow.c.consumed_at.is_(None),
                )
                .with_for_update()
            )
            .mappings()
            .first()
        )
        if row is None:
            raise MemberError("SIGN_IN_FAILED")
        captured = dict(row)
        # Keep only the replay tombstone. The caller receives these secrets once.
        c.execute(
            update(flow)
            .where(flow.c.hash == row["hash"])
            .values(consumed_at=now, nonce="", verifier="", browser_hash="", invitation_hash=None)
        )
        return captured


def read_preferences(uow: UnitOfWork, account_id: UUID) -> dict[str, Any]:
    with uow.engine.connect() as c:
        row = (
            c.execute(select(preferences).where(preferences.c.account_id == account_id))
            .mappings()
            .one()
        )
        return {k: row[k] for k in ("version", "theme", "watchlist")}


def update_preferences(
    uow: UnitOfWork, account_id: UUID, version: int, theme: str, watchlist: list[UUID]
) -> dict[str, Any]:
    if (
        theme not in ("system", "light", "dark")
        or len(watchlist) > 100
        or len(set(watchlist)) != len(watchlist)
    ):
        raise MemberError("INVALID_PREFERENCES")
    with uow.engine.begin() as c:
        row = (
            c.execute(
                update(preferences)
                .where(preferences.c.account_id == account_id, preferences.c.version == version)
                .values(version=version + 1, theme=theme, watchlist=[str(x) for x in watchlist])
                .returning(preferences)
            )
            .mappings()
            .first()
        )
        if row is None:
            raise MemberError("PREFERENCES_CONFLICT")
        return {k: row[k] for k in ("version", "theme", "watchlist")}


def bind_manager(
    uow: UnitOfWork, account_id: UUID, manager_id: UUID, season: int, actor: UUID
) -> None:
    now = datetime.now(UTC)
    with uow.engine.begin() as c:
        if (
            c.scalar(select(account.c.id).where(account.c.id == account_id).with_for_update())
            is None
        ):
            raise MemberError("ACCOUNT_NOT_FOUND")
        c.execute(
            select(
                func.pg_advisory_xact_lock(int(digest(f"binding:{season}:{manager_id}")[:15], 16))
            )
        )
        owner = c.scalar(
            select(binding.c.account_id).where(
                binding.c.manager_id == manager_id,
                binding.c.season == season,
                binding.c.revoked_at.is_(None),
            )
        )
        if owner is not None and owner != account_id:
            raise MemberError("BINDING_CONFLICT")
        c.execute(
            pg_insert(binding)
            .values(
                account_id=account_id,
                manager_id=manager_id,
                season=season,
                approved_by=actor,
                approved_at=now,
            )
            .on_conflict_do_update(
                index_elements=[binding.c.account_id, binding.c.season, binding.c.manager_id],
                set_={"approved_by": actor, "approved_at": now, "revoked_at": None},
            )
        )
        c.execute(
            update(session)
            .where(session.c.account_id == account_id, session.c.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        c.execute(
            insert(audit).values(
                actor_id=actor, target_id=account_id, action="manager.bound", occurred_at=now
            )
        )


def revoke_binding(
    uow: UnitOfWork, account_id: UUID, manager_id: UUID, season: int, actor: UUID
) -> None:
    now = datetime.now(UTC)
    with uow.engine.begin() as c:
        if (
            c.scalar(select(account.c.id).where(account.c.id == account_id).with_for_update())
            is None
        ):
            raise MemberError("ACCOUNT_NOT_FOUND")
        c.execute(
            update(binding)
            .where(
                binding.c.account_id == account_id,
                binding.c.manager_id == manager_id,
                binding.c.season == season,
            )
            .values(revoked_at=now)
        )
        c.execute(
            update(session)
            .where(session.c.account_id == account_id, session.c.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        c.execute(
            insert(audit).values(
                actor_id=actor, target_id=account_id, action="manager.unbound", occurred_at=now
            )
        )


def list_accounts(uow: UnitOfWork, season: int) -> list[dict[str, Any]]:
    with uow.engine.connect() as c:
        accounts = [
            dict(row)
            for row in c.execute(
                select(account.c.id, account.c.display_name, account.c.role, account.c.suspended)
                .order_by(account.c.created_at, account.c.id)
                .limit(100)
            ).mappings()
        ]
        approved: dict[UUID, list[UUID]] = {row["id"]: [] for row in accounts}
        if approved:
            for row in c.execute(
                select(binding.c.account_id, binding.c.manager_id)
                .where(
                    binding.c.account_id.in_(approved),
                    binding.c.season == season,
                    binding.c.revoked_at.is_(None),
                )
                .order_by(binding.c.manager_id)
            ):
                approved[row.account_id].append(row.manager_id)
        return [{**row, "manager_ids": approved[row["id"]]} for row in accounts]


def manager_ids(uow: UnitOfWork, account_id: UUID, season: int) -> set[UUID]:
    with uow.engine.connect() as c:
        return set(
            c.scalars(
                select(binding.c.manager_id).where(
                    and_(
                        binding.c.account_id == account_id,
                        binding.c.season == season,
                        binding.c.revoked_at.is_(None),
                    )
                )
            )
        )
