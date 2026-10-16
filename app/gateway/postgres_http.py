
"""HTTP boundary for PostgreSQL-backed runtime inference."""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError

from app.contracts import ModelRequest

from app.gateway.postgres_orchestrator import (
    OrchestrationResult,
    ResponseBlockedError,
    run_postgres_inference,
)

from app.gateway.postgres_session_resolver import (
    InvalidDatabaseIdentity,
    SessionAccessDenied,
)

from app.providers.errors import ProviderError


# ==================================================
# VALIDATION
# ==================================================

def _valid_uuid(value: str) -> bool:
    """Check that an identity or session ID is a UUID."""

    try:
        UUID(value)
        return True

    except (ValueError, TypeError, AttributeError):
        return False


# ==================================================
# SAFE HTTP ERRORS
# ==================================================

def _safe_error(
    status_code: int,
    code: str,
    message: str,
    request_id: str,
) -> HTTPException:
    """Return a sanitized error with a correlation header."""

    return HTTPException(
        status_code=status_code,
        detail={
            "code": code,
            "message": message,
            "request_id": request_id,
        },
        headers={
            "X-Request-ID": request_id,
        },
    )


# ==================================================
# POSTGRESQL RUNTIME HTTP BOUNDARY
# ==================================================

async def generate_postgres_response(
    *,
    model_request: ModelRequest,
    provider_router,
    db,
    requested_session_id: str | None,
) -> OrchestrationResult:
    """Run PostgreSQL inference with sanitized HTTP errors."""

    request_id = model_request.request_id
    identity = model_request.trusted_context

    # ==================================================
    # 1. VALIDATE TRUSTED DATABASE IDENTITY
    # ==================================================

    # Trusted identity comes from server-side authentication.
    # Invalid tenant/agent configuration is a server error.
    if not (
        _valid_uuid(identity.tenant_id)
        and _valid_uuid(identity.agent_id)
    ):
        raise _safe_error(
            503,
            "runtime_configuration_error",
            "The runtime is not configured correctly.",
            request_id,
        )

    # ==================================================
    # 2. VALIDATE CLIENT SESSION ID
    # ==================================================

    # The requested session ID is client-supplied.
    if (
        requested_session_id is not None
        and not _valid_uuid(requested_session_id)
    ):
        raise _safe_error(
            400,
            "invalid_session_id",
            "Invalid PostgreSQL session ID.",
            request_id,
        )

    # ==================================================
    # 3. EXECUTE AUTHORIZED POSTGRESQL INFERENCE
    # ==================================================

    try:
        return await run_postgres_inference(
            model_request=model_request,
            provider_router=provider_router,
            db=db,
            requested_session_id=requested_session_id,
        )

    # ==================================================
    # 4. DATABASE IDENTITY ERRORS
    # ==================================================

    except InvalidDatabaseIdentity as exc:
        raise _safe_error(
            503,
            "runtime_configuration_error",
            "The runtime is not configured correctly.",
            request_id,
        ) from exc

    # ==================================================
    # 5. TENANT OR SESSION AUTHORIZATION ERRORS
    # ==================================================

    except SessionAccessDenied as exc:
        raise _safe_error(
            403,
            "session_access_denied",
            "Session access is not authorized.",
            request_id,
        ) from exc

    # ==================================================
    # 6. SECURITY INSPECTION BLOCKS
    # ==================================================

    except ResponseBlockedError as exc:
        raise _safe_error(
            403,
            "response_blocked",
            (
                "The model response was blocked "
                "by AegisTwin security policy."
            ),
            request_id,
        ) from exc

    # ==================================================
    # 7. PROVIDER ERRORS
    # ==================================================

    except ProviderError:
        # Let the existing gateway route apply its
        # established sanitized provider-error mapping.
        raise

    # ==================================================
    # 8. POSTGRESQL FAILURES
    # ==================================================

    except SQLAlchemyError as exc:
        raise _safe_error(
            503,
            "database_unavailable",
            "The runtime database is unavailable.",
            request_id,
        ) from exc

    # ==================================================
    # 9. UNEXPECTED INTERNAL FAILURES
    # ==================================================

    except Exception as exc:
        # Fail closed for unexpected internal/audit failures.
        # Do not expose queries, secrets or tracebacks.
        raise _safe_error(
            503,
            "runtime_internal_error",
            "The runtime could not complete the request.",
            request_id,
        ) from exc
