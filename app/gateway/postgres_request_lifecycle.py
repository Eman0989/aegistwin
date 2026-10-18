
"""Tenant-scoped PostgreSQL request lifecycle adapter."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import timedelta
from uuid import UUID, uuid4

from sqlalchemy import func, update
from sqlalchemy.orm import Session

from app.contracts import TrustedIdentityContext
from app.gateway.postgres_session_resolver import (
    resolve_existing_session,
)
from app.infrastructure.models import AgentRequest
from app.infrastructure.persistence import complete_request


ALLOWED_FINAL_STATUSES = {
    "completed",
    "failed",
    "blocked",
}

ALLOWED_ERROR_CODES = {
    "invalid_request",
    "unsupported_provider",
    "unsupported_temperature",
    "streaming_not_supported",
    "model_not_found",
    "rate_limited",
    "provider_timeout",
    "provider_unavailable",
    "invalid_credentials",
    "provider_error",
    "response_blocked",
}


class RequestFinalizationError(RuntimeError):
    """A pending request could not be safely finalized."""


class RequestLeaseCreationError(RuntimeError):
    """A request could not be created with its initial lease."""


@dataclass(frozen=True)
class PersistedRequest:
    request_id: UUID
    tenant_id: UUID
    agent_id: UUID
    session_id: UUID
    public_request_id: str
    lease_token: str | None = None


def attach_lease(
    request: PersistedRequest,
    lease_token: str,
) -> PersistedRequest:
    """Associate an acquired lease with a persisted request."""

    if not isinstance(lease_token, str) or not lease_token:
        raise ValueError("Invalid request lease token.")

    return replace(
        request,
        lease_token=lease_token,
    )


def start_request(
    *,
    identity: TrustedIdentityContext,
    public_request_id: str,
    provider: str,
    model: str,
    db: Session,
) -> PersistedRequest:
    """Authorize and insert a pending request.

    The caller owns the database transaction.
    No commit is performed here.
    """

    resolved = resolve_existing_session(
        identity=identity,
        db=db,
    )

    database_request = AgentRequest(
        tenant_id=resolved.tenant_id,
        agent_id=resolved.agent_id,
        session_id=resolved.session_id,
        provider=provider,
        model=model,
        status="pending",
        public_request_id=public_request_id,
    )

    db.add(database_request)
    db.flush()

    return PersistedRequest(
        request_id=database_request.id,
        tenant_id=resolved.tenant_id,
        agent_id=resolved.agent_id,
        session_id=resolved.session_id,
        public_request_id=public_request_id,
    )


def start_leased_request(
    *,
    identity: TrustedIdentityContext,
    public_request_id: str,
    provider: str,
    model: str,
    worker_id: str,
    db: Session,
    lease_seconds: int = 60,
) -> PersistedRequest:
    """Insert a pending request and acquire its initial lease.

    Both operations use the caller's database transaction.

    The caller must commit before provider inference.
    If the transaction rolls back, neither the pending
    request nor its initial lease is persisted.
    """

    if (
        not isinstance(worker_id, str)
        or not worker_id.strip()
        or len(worker_id) > 150
    ):
        raise ValueError("Invalid worker ID.")

    if (
        type(lease_seconds) is not int
        or not 1 <= lease_seconds <= 86400
    ):
        raise ValueError("Invalid lease duration.")

    lease_token = uuid4().hex

    # This creates the request but does not commit it.
    persisted = start_request(
        identity=identity,
        public_request_id=public_request_id,
        provider=provider,
        model=model,
        db=db,
    )

    # Assign ownership inside the SAME transaction.
    statement = (
        update(AgentRequest)
        .where(
            AgentRequest.id == persisted.request_id,
            AgentRequest.tenant_id == persisted.tenant_id,
            AgentRequest.status == "pending",
            AgentRequest.lease_owner_id.is_(None),
            AgentRequest.lease_token.is_(None),
            AgentRequest.lease_expires_at.is_(None),
        )
        .values(
            lease_owner_id=worker_id,
            lease_token=lease_token,
            lease_expires_at=(
                func.clock_timestamp()
                + timedelta(seconds=lease_seconds)
            ),
            last_heartbeat_at=func.clock_timestamp(),
        )
        .returning(AgentRequest.id)
    )

    claimed_id = db.execute(
        statement
    ).scalar_one_or_none()

    if claimed_id != persisted.request_id:
        raise RequestLeaseCreationError(
            "Initial request lease assignment failed."
        )

    return attach_lease(
        request=persisted,
        lease_token=lease_token,
    )


def finish_request(
    *,
    request: PersistedRequest,
    outcome: str,
    latency_ms: float | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    error_code: str | None = None,
) -> UUID:
    """Finalize a request, failing closed on rejection."""

    if outcome not in ALLOWED_FINAL_STATUSES:
        raise ValueError("Unsupported request outcome.")

    if error_code is not None:
        error_code = (
            error_code
            if error_code in ALLOWED_ERROR_CODES
            else "provider_error"
        )

    if outcome == "blocked":
        error_code = "response_blocked"

    arguments = {
        "request_id": request.request_id,
        "tenant_id": request.tenant_id,
        "status": outcome,
        "latency": latency_ms,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "error_code": error_code,
    }

    if request.lease_token is not None:
        arguments["lease_token"] = request.lease_token

    result = complete_request(**arguments)

    if result is None:
        raise RequestFinalizationError(
            "Request finalization was rejected."
        )

    if result != request.request_id:
        raise RequestFinalizationError(
            "Request finalization returned an unexpected ID."
        )

    return result
