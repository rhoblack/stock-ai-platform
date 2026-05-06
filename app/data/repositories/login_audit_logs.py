"""Repository for v0.8 Phase B LoginAuditLog rows.

The repository is intentionally append-only: there is no `update` / `delete`
helper. Operators who need retention enforcement should add a separate purge
script in a later cycle.

source_ip / user_agent are SHA256-hashed by the caller (auth route) via
``app.auth.security.hash_for_audit`` before reaching this repository -- raw
values are NEVER persisted. The tests assert this contract.
"""

from __future__ import annotations

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.data.repositories.base import BaseRepository
from app.db.models import LoginAuditLog


EVENT_LOGIN_SUCCESS = "LOGIN_SUCCESS"
EVENT_LOGIN_FAILED = "LOGIN_FAILED"
EVENT_LOGOUT = "LOGOUT"
# v0.9 Phase A: recorded when a login attempt is rejected by the in-memory
# brute force guard before credentials are checked. The DB column is VARCHAR
# so no migration is needed -- this is a new valid enum value only.
EVENT_LOCKOUT_REJECTED = "LOCKOUT_REJECTED"

EVENT_TYPES = (EVENT_LOGIN_SUCCESS, EVENT_LOGIN_FAILED, EVENT_LOGOUT, EVENT_LOCKOUT_REJECTED)


class LoginAuditLogRepository(BaseRepository[LoginAuditLog]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, LoginAuditLog)

    def create(
        self,
        *,
        event_type: str,
        username: str | None,
        user_id: int | None,
        source_ip_hash: str | None,
        user_agent_hash: str | None,
    ) -> LoginAuditLog:
        if event_type not in EVENT_TYPES:
            raise ValueError(
                f"event_type must be one of {EVENT_TYPES!r}, got {event_type!r}"
            )
        return self.add(
            LoginAuditLog(
                event_type=event_type,
                username=username,
                user_id=user_id,
                source_ip_hash=source_ip_hash,
                user_agent_hash=user_agent_hash,
            ),
        )

    def list_recent(self, *, limit: int = 50) -> list[LoginAuditLog]:
        statement = (
            select(LoginAuditLog)
            .order_by(desc(LoginAuditLog.created_at), desc(LoginAuditLog.id))
            .limit(limit)
        )
        return list(self.session.execute(statement).scalars().all())

    def list_by_username(
        self,
        username: str,
        *,
        limit: int = 50,
    ) -> list[LoginAuditLog]:
        statement = (
            select(LoginAuditLog)
            .where(LoginAuditLog.username == username)
            .order_by(desc(LoginAuditLog.created_at), desc(LoginAuditLog.id))
            .limit(limit)
        )
        return list(self.session.execute(statement).scalars().all())

    def list_by_user(self, user_id: int, *, limit: int = 50) -> list[LoginAuditLog]:
        statement = (
            select(LoginAuditLog)
            .where(LoginAuditLog.user_id == user_id)
            .order_by(desc(LoginAuditLog.created_at), desc(LoginAuditLog.id))
            .limit(limit)
        )
        return list(self.session.execute(statement).scalars().all())
