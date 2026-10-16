
"""Tenant-scoped PostgreSQL request lifecycle adapter."""

from __future__ import annotations

from dataclasses import dataclass, replace
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


class RequestFinalizationError(RuntimeError):
    """A pending request could not be safely finalized."""


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
    """Associate an acquired lease with the persisted request."""

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

    The caller must commit the transaction before
    starting provider inference.
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


def finish_request(
    *,
    request: PersistedRequest,
    outcome: str,
    latency_ms: float | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    error_code: str | None = None,
) -> UUID:
    """Finalize one pending request, failing closed on rejection.

    A leased request must present its valid, unexpired
    token. An unsuccessful conditional database update
    must never be mistaken for successful auditing.
    """

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
