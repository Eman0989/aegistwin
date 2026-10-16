
"""PostgreSQL-backed inference with leased audit execution."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
from math import isfinite
from typing import Protocol
from uuid import uuid4

from sqlalchemy.orm import Session

from app.contracts import ModelRequest, ModelResponse
from app.gateway.postgres_request_lifecycle import (
    PersistedRequest,
    attach_lease,
    finish_request,
    start_request,
)
from app.gateway.postgres_session_manager import (
    manage_postgres_session,
)
from app.infrastructure.persistence import (
    acquire_request_lease,
    renew_request_lease,
)
from app.providers.errors import ProviderError
from app.security.llm_response_inspector import (
    ResponseAction,
    inspect_response,
)


LEASE_SECONDS = 60
HEARTBEAT_SECONDS = 20


class ProviderProtocol(Protocol):
    async def generate(
        self,
        request: ModelRequest,
    ) -> ModelResponse:
        ...


class ResponseBlockedError(Exception):
    """The generated response cannot be released."""


class RequestLeaseError(RuntimeError):
    """Worker ownership could not be established or maintained."""


@dataclass(frozen=True)
class OrchestrationResult:
    response: ModelResponse
    session_id: str


# ==========================================================
# WORKER LEASE AND HEARTBEAT
# ==========================================================


def _acquire_lease(
    persisted: PersistedRequest,
    worker_id: str,
) -> PersistedRequest:
    """Claim the committed request before provider inference."""

    token = acquire_request_lease(
        tenant_id=persisted.tenant_id,
        request_id=persisted.request_id,
        worker_id=worker_id,
        lease_seconds=LEASE_SECONDS,
    )

    if not isinstance(token, str) or not token:
        raise RequestLeaseError(
            "Request lease acquisition was rejected."
        )

    return attach_lease(
        request=persisted,
        lease_token=token,
    )


@asynccontextmanager
async def _lease_heartbeat(
    persisted: PersistedRequest,
    worker_id: str,
):
    """Renew the request lease during asynchronous inference.

    The heartbeat uses a worker thread for synchronous
    SQLAlchemy I/O, avoiding blocking the event loop.

    On heartbeat failure, prevent the response from
    being treated as successfully audited.
    """

    stop_event = asyncio.Event()
    ownership_lost = asyncio.Event()

    async def heartbeat_loop():
        while not stop_event.is_set():
            try:
                await asyncio.wait_for(
                    stop_event.wait(),
                    timeout=HEARTBEAT_SECONDS,
                )
                break
            except asyncio.TimeoutError:
                pass

            try:
                renewed = await asyncio.to_thread(
                    renew_request_lease,
                    tenant_id=persisted.tenant_id,
                    request_id=persisted.request_id,
                    worker_id=worker_id,
                    lease_token=persisted.lease_token,
                    lease_seconds=LEASE_SECONDS,
                )
            except Exception:
                ownership_lost.set()
                return

            if not renewed:
                ownership_lost.set()
                return

    task = asyncio.create_task(heartbeat_loop())

    try:
        yield ownership_lost
    finally:
        stop_event.set()

        # Allow an in-flight renewal to settle before the
        # orchestrator attempts audit finalization.
        await task


# ==========================================================
# RESPONSE INSPECTION
# ==========================================================


def _blocked(message: str) -> ResponseBlockedError:
    return ResponseBlockedError(message)


def _validate_response(
    response,
    request: ModelRequest,
) -> None:
    """Reject responses that do not match the request."""

    if (
        not isinstance(response, ModelResponse)
        or response.request_id != request.request_id
        or response.provider != request.provider
        or response.model != request.model
    ):
        raise _blocked(
            "The model response failed integrity validation."
        )


def _inspect_and_validate(
    response: ModelResponse,
    request: ModelRequest,
) -> ModelResponse:
    """Inspect output and validate safe response metadata."""

    _validate_response(response, request)

    try:
        inspection = inspect_response(response.content)
    except Exception:
        raise _blocked(
            "The model response was blocked by security policy."
        ) from None

    if inspection.action == ResponseAction.BLOCK:
        raise _blocked(
            "The model response was blocked by security policy."
        )

    if inspection.action == ResponseAction.REDACT:
        if not isinstance(inspection.content, str):
            raise _blocked(
                "The model response was blocked by security policy."
            )

        response = response.model_copy(
            update={"content": inspection.content}
        )

    elif inspection.action == ResponseAction.ALLOW:
        if (
            not isinstance(inspection.content, str)
            or inspection.content != response.content
        ):
            raise _blocked(
                "The model response failed inspection validation."
            )

    else:
        raise _blocked(
            "The model response was blocked by security policy."
        )

    usage = response.usage

    def valid_token_count(value):
        return (
            value is None
            or (
                type(value) is int
                and value >= 0
            )
        )

    if (
        not isinstance(usage, dict)
        or not valid_token_count(usage.get("input_tokens"))
        or not valid_token_count(usage.get("output_tokens"))
        or not isinstance(response.latency_ms, (int, float))
        or isinstance(response.latency_ms, bool)
        or not isfinite(response.latency_ms)
        or response.latency_ms < 0
    ):
        raise _blocked(
            "The model response failed usage validation."
        )

    return response


# ==========================================================
# AUTHORIZED POSTGRESQL INFERENCE
# ==========================================================


async def run_postgres_inference(
    *,
    model_request: ModelRequest,
    provider_router: ProviderProtocol,
    db: Session,
    requested_session_id: str | None,
) -> OrchestrationResult:
    """Execute one tenant-authorized, leased model request."""

    # 1. Authorize or create the PostgreSQL session.
    managed = manage_postgres_session(
        identity=model_request.trusted_context,
        db=db,
        requested_session_id=requested_session_id,
    )

    authorized_request = model_request.model_copy(
        update={"trusted_context": managed.identity}
    )

    # 2. Insert pending audit record.
    persisted = start_request(
        identity=managed.identity,
        public_request_id=authorized_request.request_id,
        provider=authorized_request.provider,
        model=authorized_request.model,
        db=db,
    )

    # The record must exist in PostgreSQL before inference.
    db.commit()

    # 3. Acquire exclusive worker ownership.
    worker_id = f"aegis-worker-{uuid4().hex}"

    # Run synchronous database operations outside the event loop.
    persisted = await asyncio.to_thread(
        _acquire_lease,
        persisted,
        worker_id,
    )

    # 4. Provider inference with heartbeat renewal.
    try:
        async with _lease_heartbeat(
            persisted,
            worker_id,
        ) as ownership_lost:
            try:
                response = await provider_router.generate(
                    authorized_request
                )
                provider_error = None

            except Exception as exc:
                response = None
                provider_error = exc

        # Never continue if ownership was lost.
        if ownership_lost.is_set():
            raise RequestLeaseError(
                "Request lease ownership was lost."
            )

    except asyncio.CancelledError:
        # Cancellation must not release any model content.
        # The expired request can later be recovered.
        raise

    # 5. Audit provider failures before propagating them.
    if provider_error is not None:
        if isinstance(provider_error, ProviderError):
            finish_request(
                request=persisted,
                outcome="failed",
                error_code=provider_error.code,
            )
        else:
            finish_request(
                request=persisted,
                outcome="failed",
                error_code="provider_error",
            )

        raise provider_error

    # 6. Integrity validation and post-LLM inspection.
    try:
        response = _inspect_and_validate(
            response,
            authorized_request,
        )

    except ResponseBlockedError:
        finish_request(
            request=persisted,
            outcome="blocked",
        )
        raise

    # 7. Finalize audit while the lease is valid.
    # finish_request raises if conditional finalization fails.
    finish_request(
        request=persisted,
        outcome="completed",
        latency_ms=response.latency_ms,
        input_tokens=response.usage.get("input_tokens"),
        output_tokens=response.usage.get("output_tokens"),
    )

    # 8. Only successfully audited output reaches the client.
    return OrchestrationResult(
        response=response,
        session_id=str(managed.session_id),
    )
