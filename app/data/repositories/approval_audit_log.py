"""Repository for v0.15 Phase D ApprovalAuditLog rows.

Append-only audit trail for the Approval Workflow. NO update / delete
methods exist by design -- once a row is committed, it is immutable from
the application's perspective. The downstream Approval API surfaces the
rows via ``GET /api/approvals/audit`` only.

Raw IP / user-agent values are NEVER stored. Callers must pass
``ip_hash`` / ``user_agent_hash`` already computed via
:func:`app.auth.security.hash_for_audit` (SHA256 hex, 64 chars).

Forbidden ``details_json`` keys (validated below): ``api_key``, ``token``,
``secret``, ``access_token``, ``jwt_secret``, ``broker_order_id``,
``kis_order_id``, ``real_account``, ``real_order_id``, ``account_number``,
``raw_text``, ``body``, ``full_text``, ``source_file_path``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.data.repositories.base import BaseRepository
from app.db.models import ApprovalAuditLog


VALID_EVENT_TYPES: frozenset[str] = frozenset(
    {
        "CREATED",
        "RISK_CHECKED",
        "RISK_REJECTED",
        "APPROVED",
        "REJECTED",
        "EXPIRED",
        "EXECUTED_PAPER",
        "KILL_SWITCH_BLOCKED",
    }
)

# Forbidden keys in ``details_json``. Application-side guard so an
# accidental ApprovalService change cannot leak secret / KIS / real-broker
# fields into audit storage.
_FORBIDDEN_DETAILS_KEYS: frozenset[str] = frozenset(
    {
        "api_key",
        "token",
        "secret",
        "access_token",
        "jwt_secret",
        "broker_order_id",
        "kis_order_id",
        "real_account",
        "real_order_id",
        "account_number",
        "raw_text",
        "body",
        "full_text",
        "source_file_path",
    }
)


class ApprovalAuditLogValidationError(ValueError):
    """Raised when append() is called with malformed inputs."""


class ApprovalAuditLogRepository(BaseRepository[ApprovalAuditLog]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, ApprovalAuditLog)

    # -------- write -- append only --------

    def append(
        self,
        *,
        candidate_id: int,
        event_type: str,
        user_id: int | None = None,
        reason: str | None = None,
        details: dict[str, Any] | None = None,
        ip_hash: str | None = None,
        user_agent_hash: str | None = None,
    ) -> ApprovalAuditLog:
        """Insert one immutable audit row.

        ``ip_hash`` / ``user_agent_hash`` MUST already be SHA256 hex (64
        chars). The repository does NOT hash for you -- that is the
        route layer's job via :func:`app.auth.security.hash_for_audit`,
        keeping all hashing decisions in one place.
        """
        if event_type not in VALID_EVENT_TYPES:
            raise ApprovalAuditLogValidationError(
                f"event_type must be one of {sorted(VALID_EVENT_TYPES)} "
                f"(got {event_type!r})"
            )
        if details is not None:
            if not isinstance(details, dict):
                raise ApprovalAuditLogValidationError(
                    "details must be a dict (JSON-serialisable)"
                )
            leaked = {str(k) for k in details.keys()} & _FORBIDDEN_DETAILS_KEYS
            if leaked:
                raise ApprovalAuditLogValidationError(
                    f"details_json contains forbidden keys: {sorted(leaked)}"
                )
        if ip_hash is not None and len(ip_hash) > 64:
            raise ApprovalAuditLogValidationError(
                "ip_hash must be at most 64 chars (SHA256 hex)"
            )
        if user_agent_hash is not None and len(user_agent_hash) > 64:
            raise ApprovalAuditLogValidationError(
                "user_agent_hash must be at most 64 chars (SHA256 hex)"
            )

        return self.add(
            ApprovalAuditLog(
                candidate_id=candidate_id,
                event_type=event_type,
                user_id=user_id,
                reason=reason[:256] if reason else None,
                details_json=details,
                ip_hash=ip_hash,
                user_agent_hash=user_agent_hash,
            )
        )

    # -------- read --------

    def list_by_candidate(
        self, candidate_id: int, *, limit: int = 200
    ) -> list[ApprovalAuditLog]:
        statement = (
            select(ApprovalAuditLog)
            .where(ApprovalAuditLog.candidate_id == candidate_id)
            .order_by(ApprovalAuditLog.id.asc())
            .limit(limit)
        )
        return list(self.session.execute(statement).scalars().all())

    def list_recent(
        self,
        *,
        event_type: str | None = None,
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[ApprovalAuditLog]:
        statement = select(ApprovalAuditLog)
        if event_type is not None:
            if event_type not in VALID_EVENT_TYPES:
                raise ApprovalAuditLogValidationError(
                    f"event_type must be one of {sorted(VALID_EVENT_TYPES)}"
                )
            statement = statement.where(ApprovalAuditLog.event_type == event_type)
        if since is not None:
            statement = statement.where(ApprovalAuditLog.created_at >= since)
        statement = statement.order_by(ApprovalAuditLog.id.desc()).limit(limit)
        return list(self.session.execute(statement).scalars().all())


__all__ = [
    "ApprovalAuditLogRepository",
    "ApprovalAuditLogValidationError",
    "VALID_EVENT_TYPES",
]
