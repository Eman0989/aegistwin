
"""Tests for PostgreSQL-backed runtime HTTP error handling."""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import OperationalError

from app.contracts import (
    ModelRequest,
    ModelResponse,
    TrustedIdentityContext,
)
from app.gateway.postgres_http import generate_postgres_response
from app.gateway.postgres_orchestrator import (
    OrchestrationResult,
    ResponseBlockedError,
)
from app.gateway.postgres_session_resolver import (
    InvalidDatabaseIdentity,
    SessionAccessDenied,
)


def make_request():
    """Create a valid trusted model request for testing."""

    return ModelRequest(
        request_id="REQ-http-test",
        provider="ollama",
        model="llama3.2:3b",
        messages=[],
        trusted_context=TrustedIdentityContext(
            tenant_id=str(uuid4()),
            user_id="test-user",
            agent_id=str(uuid4()),
            session_id="SES-legacy",
        ),
    )


# ==================================================
# 1. SUCCESSFUL POSTGRESQL RESPONSE
# ==================================================

@pytest.mark.asyncio
async def test_successful_postgres_response():
    request = make_request()

    expected = OrchestrationResult(
        response=ModelResponse(
            request_id=request.request_id,
            provider=request.provider,
            model=request.model,
            content="Hello.",
        ),
        session_id=str(uuid4()),
    )

    with patch(
        "app.gateway.postgres_http.run_postgres_inference",
        new_callable=AsyncMock,
    ) as mock_run:
        mock_run.return_value = expected

        result = await generate_postgres_response(
            model_request=request,
            provider_router=object(),
            db=object(),
            requested_session_id=None,
        )

    assert result == expected
    mock_run.assert_awaited_once()


# ==================================================
# 2. SANITIZED HTTP ERROR RESPONSES
# ==================================================

@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "expected_status", "expected_code"),
    [
        (
            InvalidDatabaseIdentity("Invalid UUID"),
            503,
            "runtime_configuration_error",
        ),
        (
            SessionAccessDenied("Foreign session"),
            403,
            "session_access_denied",
        ),
        (
            ResponseBlockedError("Unsafe response"),
            403,
            "response_blocked",
        ),
        (
            OperationalError(
                "SELECT 1",
                {},
                Exception("database disconnected"),
            ),
            503,
            "database_unavailable",
        ),
    ],
)
async def test_safe_http_errors(
    error,
    expected_status,
    expected_code,
):
    request = make_request()

    with patch(
        "app.gateway.postgres_http.run_postgres_inference",
        new_callable=AsyncMock,
    ) as mock_run:
        mock_run.side_effect = error

        with pytest.raises(HTTPException) as exc:
            await generate_postgres_response(
                model_request=request,
                provider_router=object(),
                db=object(),
                requested_session_id=None,
            )

    assert exc.value.status_code == expected_status
    assert exc.value.detail["code"] == expected_code
    assert exc.value.detail["request_id"] == request.request_id

    # Never expose internal database or authorization details.
    assert "database disconnected" not in str(exc.value.detail)
    assert "Foreign session" not in str(exc.value.detail)
    assert "Invalid UUID" not in str(exc.value.detail)


# ==================================================
# 3. INVALID CLIENT SESSION ID -> HTTP 400
# ==================================================

@pytest.mark.asyncio
async def test_invalid_client_session_returns_400():
    request = make_request()

    with patch(
        "app.gateway.postgres_http.run_postgres_inference",
        new_callable=AsyncMock,
    ) as mock_run:

        with pytest.raises(HTTPException) as exc:
            await generate_postgres_response(
                model_request=request,
                provider_router=object(),
                db=object(),
                requested_session_id="SES-not-a-uuid",
            )

        mock_run.assert_not_awaited()

    assert exc.value.status_code == 400
    assert exc.value.detail["code"] == "invalid_session_id"
    assert exc.value.detail["request_id"] == request.request_id


# ==================================================
# 4. INVALID TRUSTED TENANT ID -> HTTP 503
# ==================================================

@pytest.mark.asyncio
async def test_invalid_trusted_tenant_returns_503():
    request = make_request()

    request.trusted_context.tenant_id = "tenant-demo"

    with patch(
        "app.gateway.postgres_http.run_postgres_inference",
        new_callable=AsyncMock,
    ) as mock_run:

        with pytest.raises(HTTPException) as exc:
            await generate_postgres_response(
                model_request=request,
                provider_router=object(),
                db=object(),
                requested_session_id=None,
            )

        mock_run.assert_not_awaited()

    assert exc.value.status_code == 503

    assert (
        exc.value.detail["code"]
        == "runtime_configuration_error"
    )

    assert exc.value.detail["request_id"] == request.request_id
    assert "tenant-demo" not in str(exc.value.detail)

from app.providers.errors import ProviderError


@pytest.mark.asyncio
async def test_provider_error_preserved_for_route():
    request = make_request()

    provider_error = ProviderError(
        "Secret provider diagnostic",
        code="provider_unavailable",
        retryable=True,
    )

    with patch(
        "app.gateway.postgres_http.run_postgres_inference",
        new_callable=AsyncMock,
        side_effect=provider_error,
    ):
        with pytest.raises(ProviderError) as exc:
            await generate_postgres_response(
                model_request=request,
                provider_router=object(),
                db=object(),
                requested_session_id=None,
            )

    assert exc.value.code == "provider_unavailable"


@pytest.mark.asyncio
async def test_unexpected_internal_error_is_sanitized():
    request = make_request()

    with patch(
        "app.gateway.postgres_http.run_postgres_inference",
        new_callable=AsyncMock,
        side_effect=RuntimeError(
            "PRIVATE_DATABASE_PASSWORD"
        ),
    ):
        with pytest.raises(HTTPException) as exc:
            await generate_postgres_response(
                model_request=request,
                provider_router=object(),
                db=object(),
                requested_session_id=None,
            )

    assert exc.value.status_code == 503
    assert exc.value.detail["code"] == "runtime_internal_error"
    assert "PRIVATE_DATABASE_PASSWORD" not in str(exc.value.detail)


@pytest.mark.asyncio
async def test_invalid_trusted_agent_returns_503():
    request = make_request()
    request.trusted_context.agent_id = "invalid-agent"

    with patch(
        "app.gateway.postgres_http.run_postgres_inference",
        new_callable=AsyncMock,
    ) as mock_run:
        with pytest.raises(HTTPException) as exc:
            await generate_postgres_response(
                model_request=request,
                provider_router=object(),
                db=object(),
                requested_session_id=None,
            )

        mock_run.assert_not_awaited()

    assert exc.value.status_code == 503
    assert exc.value.detail["code"] == "runtime_configuration_error"
