
"""Tenant-scoped PostgreSQL request lifecycle adapter."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

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


@dataclass(frozen=True)
class PersistedRequest:
    request_id: UUID
    tenant_id: UUID
    agent_id: UUID
    session_id: UUID
    public_request_id: str


def start_request(
    *,
    identity: TrustedIdentityContext,
    public_request_id: str,
    provider: str,
    model: str,
    db: Session,
) -> PersistedRequest:
    """Authorize and insert a pending request in one transaction.

    The caller owns the transaction and must commit before inference.
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


def finish_request(
    *,
    request: PersistedRequest,
    outcome: str,
    latency_ms: float | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    error_code: str | None = None,
) -> UUID:
    """Persist a validated final request outcome."""

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

    return complete_request(
        request_id=request.request_id,
        tenant_id=request.tenant_id,
        status=outcome,
        latency=latency_ms,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        error_code=error_code,
    )
