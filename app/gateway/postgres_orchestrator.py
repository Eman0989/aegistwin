
"""PostgreSQL-backed inference with atomic leases and audit execution."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
from math import isfinite
from typing import Callable, Protocol
from uuid import uuid4

from sqlalchemy.orm import Session

from app.contracts import ModelRequest, ModelResponse

from app.gateway.postgres_request_lifecycle import (
    PersistedRequest,
    finish_request,
    start_leased_request,
)
from app.gateway.postgres_session_manager import (
    manage_postgres_session,
)
from app.infrastructure.persistence import (
    renew_request_lease,
)
from app.providers.errors import ProviderError
from app.security.llm_response_inspector import (
    ResponseAction,
    inspect_response,
)


LEASE_SECONDS = 60
HEARTBEAT_SECONDS = 20


def _prepare_initial_request(
    *,
    model_request: ModelRequest,
    requested_session_id: str | None,
    worker_id: str,
    db: Session,
):
    """Authorize, create a leased request, and commit atomically.

    Called from a worker thread. Production code must create and close
    its SQLAlchemy Session inside that worker thread (follow-up change).
    """
    try:
        managed = manage_postgres_session(
            identity=model_request.trusted_context,
            db=db,
            requested_session_id=requested_session_id,
        )

        authorized_request = model_request.model_copy(
            update={"trusted_context": managed.identity}
        )

        persisted = start_leased_request(
            identity=managed.identity,
            public_request_id=authorized_request.request_id,
            provider=authorized_request.provider,
            model=authorized_request.model,
            worker_id=worker_id,
            db=db,
            lease_seconds=LEASE_SECONDS,
        )

        db.commit()

        return managed, authorized_request, persisted

    except BaseException:
        db.rollback()
        raise



def _prepare_with_session_factory(
    *,
    model_request: ModelRequest,
    requested_session_id: str | None,
    worker_id: str,
    session_factory: Callable[[], Session],
):
    """Create, use, and close a DB session within one worker thread."""

    with session_factory() as db:
        return _prepare_initial_request(
            model_request=model_request,
            requested_session_id=requested_session_id,
            worker_id=worker_id,
            db=db,
        )


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


@asynccontextmanager
async def _lease_heartbeat(
    persisted: PersistedRequest,
    worker_id: str,
):
    """Renew a request lease while provider inference is running.

    SQLAlchemy persistence operations run in a worker thread
    to avoid blocking the asynchronous event loop.

    A failed renewal marks ownership as lost. The gateway
    must not release model output after ownership loss.
    """

    if not persisted.lease_token:
        raise RequestLeaseError(
            "Request has no valid lease token."
        )

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

            if stop_event.is_set():
                break

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

        # Wait for any in-flight renewal to finish before
        # attempting audit finalization.
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
    """Reject responses that do not match their originating request."""

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
    """Inspect model output and validate response metadata."""

    _validate_response(response, request)

    try:
        inspection = inspect_response(
            response.content
        )

    except Exception:
        # Never release content that could not be inspected.
        raise _blocked(
            "The model response was blocked by security policy."
        ) from None

    # ------------------------------------------------------
    # BLOCK
    # ------------------------------------------------------

    if inspection.action == ResponseAction.BLOCK:
        raise _blocked(
            "The model response was blocked by security policy."
        )

    # ------------------------------------------------------
    # REDACT
    # ------------------------------------------------------

    if inspection.action == ResponseAction.REDACT:
        if not isinstance(inspection.content, str):
            raise _blocked(
                "The model response was blocked by security policy."
            )

        response = response.model_copy(
            update={
                "content": inspection.content,
            }
        )

    # ------------------------------------------------------
    # ALLOW
    # ------------------------------------------------------

    elif inspection.action == ResponseAction.ALLOW:
        if (
            not isinstance(inspection.content, str)
            or inspection.content != response.content
        ):
            raise _blocked(
                "The model response failed inspection validation."
            )

    # ------------------------------------------------------
    # UNKNOWN ACTION
    # ------------------------------------------------------

    else:
        raise _blocked(
            "The model response was blocked by security policy."
        )

    # ------------------------------------------------------
    # VALIDATE PROVIDER USAGE METRICS
    # ------------------------------------------------------

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
        or not valid_token_count(
            usage.get("input_tokens")
        )
        or not valid_token_count(
            usage.get("output_tokens")
        )
        or not isinstance(
            response.latency_ms,
            (int, float),
        )
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
    db: Session | None = None,
    requested_session_id: str | None = None,
    session_factory: Callable[[], Session] | None = None,
) -> OrchestrationResult:
    """Execute one tenant-authorized, leased model request.

    Security guarantees:

    - The PostgreSQL session must be authorized.
    - Request creation and initial lease are atomic.
    - The transaction commits before provider inference.
    - Heartbeat renewal maintains lease ownership.
    - Generated content is inspected before release.
    - A valid lease is required for audit finalization.
    - Finalization must succeed before returning content.
    """

    # Initial synchronous database transaction runs off the event loop.
    # Production Session lifecycle must be moved into the same worker
    # thread before deploying this intermediate change.

    worker_id = f"aegis-worker-{uuid4().hex}"

    if (db is None) == (session_factory is None):
        raise ValueError(
            "Provide exactly one of db or session_factory."
        )

    if session_factory is not None:
        managed, authorized_request, persisted = await asyncio.to_thread(
            _prepare_with_session_factory,
            model_request=model_request,
            requested_session_id=requested_session_id,
            worker_id=worker_id,
            session_factory=session_factory,
        )
    else:
        # Backward-compatible path for existing tests and callers.
        # Production HTTP requests must use session_factory.
        managed, authorized_request, persisted = await asyncio.to_thread(
            _prepare_initial_request,
            model_request=model_request,
            requested_session_id=requested_session_id,
            worker_id=worker_id,
            db=db,
        )

    # ======================================================
    # 3. PROVIDER INFERENCE WITH HEARTBEAT RENEWAL
    # ======================================================

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

        # Never continue if heartbeat renewal reported
        # that the worker lost its lease.
        if ownership_lost.is_set():
            raise RequestLeaseError(
                "Request lease ownership was lost."
            )

    except asyncio.CancelledError:
        # Cancellation must never release model output.
        # Expired leases can later be recovered.
        raise

    # ======================================================
    # 4. AUDIT PROVIDER FAILURES
    # ======================================================

    if provider_error is not None:
        if isinstance(provider_error, ProviderError):
            await asyncio.to_thread(
                finish_request,
                request=persisted,
                outcome="failed",
                error_code=provider_error.code,
            )

        else:
            await asyncio.to_thread(
                finish_request,
                request=persisted,
                outcome="failed",
                error_code="provider_error",
            )

        raise provider_error

    # ======================================================
    # 5. VERIFY AND INSPECT MODEL RESPONSE
    # ======================================================

    try:
        response = _inspect_and_validate(
            response,
            authorized_request,
        )

    except ResponseBlockedError:
        await asyncio.to_thread(
            finish_request,
            request=persisted,
            outcome="blocked",
        )
        raise

    # ======================================================
    # 6. COMPLETE POSTGRESQL AUDIT RECORD
    # ======================================================

    # A valid, unexpired lease token is required.
    #
    # finish_request() raises RequestFinalizationError
    # if PostgreSQL rejects the conditional update.
    #
    # Both ALLOW and REDACT outcomes must be audited
    # before any generated content reaches the client.

    await asyncio.to_thread(
        finish_request,
        request=persisted,
        outcome="completed",
        latency_ms=response.latency_ms,
        input_tokens=response.usage.get(
            "input_tokens"
        ),
        output_tokens=response.usage.get(
            "output_tokens"
        ),
    )

    # ======================================================
    # 7. RETURN AUTHORIZED, INSPECTED RESPONSE
    # ======================================================

    return OrchestrationResult(
        response=response,
        session_id=str(managed.session_id),
    )
