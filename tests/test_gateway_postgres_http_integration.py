
"""HTTP integration tests for opt-in PostgreSQL runtime."""

from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.contracts import ModelResponse
from app.gateway.postgres_orchestrator import OrchestrationResult
from app.gateway.routes import get_provider_router


API_PATH = "/v1/model/generate"


@pytest.fixture
def runtime_client(monkeypatch):
    """Configure authenticated requests with valid UUID identities."""

    monkeypatch.setenv("AEGISTWIN_RUNTIME_API_KEY", "test-secret-key")
    monkeypatch.setenv("AEGISTWIN_RUNTIME_TENANT_ID", str(uuid4()))
    monkeypatch.setenv("AEGISTWIN_RUNTIME_AGENT_ID", str(uuid4()))
    monkeypatch.setenv("AEGISTWIN_RUNTIME_USER_ID", "test-user")

    provider = MagicMock()
    provider.generate = AsyncMock()

    app.dependency_overrides[get_provider_router] = lambda: provider

    try:
        with TestClient(app) as client:
            yield client, provider
    finally:
        app.dependency_overrides.pop(get_provider_router, None)


def request_headers(session_id=None):
    headers = {"X-Aegis-API-Key": "test-secret-key"}

    if session_id is not None:
        headers["X-Aegis-Session-ID"] = session_id

    return headers


def request_body():
    return {
        "provider": "ollama",
        "model": "llama3.2:3b",
        "messages": [{"role": "user", "content": "Hello"}],
    }


@contextmanager
def mock_db_session():
    db = MagicMock()
    yield db


def make_result(model_request, session_id):
    return OrchestrationResult(
        response=ModelResponse(
            request_id=model_request.request_id,
            provider=model_request.provider,
            model=model_request.model,
            content="Secure response",
        ),
        session_id=session_id,
    )


def test_legacy_mode_does_not_open_postgres(runtime_client, monkeypatch):
    client, provider = runtime_client

    monkeypatch.setenv(
        "AEGISTWIN_POSTGRES_RUNTIME_ENABLED",
        "false",
    )

    provider.generate.side_effect = lambda request: make_result(
        request,
        str(uuid4()),
    ).response

    with patch("app.gateway.routes.SessionLocal") as session_local:
        response = client.post(
            API_PATH,
            json=request_body(),
            headers=request_headers(),
        )

    assert response.status_code == 200
    assert response.json()["content"] == "Secure response"
    session_local.assert_not_called()


def test_postgres_creates_session_and_returns_header(
    runtime_client,
    monkeypatch,
):
    client, provider = runtime_client

    monkeypatch.setenv(
        "AEGISTWIN_POSTGRES_RUNTIME_ENABLED",
        "true",
    )

    new_session_id = str(uuid4())

    async def fake_postgres(**kwargs):
        assert kwargs["requested_session_id"] is None
        return make_result(
            kwargs["model_request"],
            new_session_id,
        )

    with (
        patch(
            "app.gateway.routes.SessionLocal",
            mock_db_session,
        ),
        patch(
            "app.gateway.routes.generate_postgres_response",
            new_callable=AsyncMock,
            side_effect=fake_postgres,
        ) as mock_generate,
    ):
        response = client.post(
            API_PATH,
            json=request_body(),
            headers=request_headers(),
        )

    assert response.status_code == 200
    assert response.headers["X-Aegis-Session-ID"] == new_session_id
    assert response.json()["content"] == "Secure response"
    mock_generate.assert_awaited_once()
    provider.generate.assert_not_awaited()


def test_postgres_reuses_client_session(
    runtime_client,
    monkeypatch,
):
    client, _ = runtime_client

    monkeypatch.setenv(
        "AEGISTWIN_POSTGRES_RUNTIME_ENABLED",
        "true",
    )

    existing_session = str(uuid4())

    async def fake_postgres(**kwargs):
        assert kwargs["requested_session_id"] == existing_session
        return make_result(
            kwargs["model_request"],
            existing_session,
        )

    with (
        patch(
            "app.gateway.routes.SessionLocal",
            mock_db_session,
        ),
        patch(
            "app.gateway.routes.generate_postgres_response",
            new_callable=AsyncMock,
            side_effect=fake_postgres,
        ),
    ):
        response = client.post(
            API_PATH,
            json=request_body(),
            headers=request_headers(existing_session),
        )

    assert response.status_code == 200
    assert response.headers["X-Aegis-Session-ID"] == existing_session


def test_invalid_feature_flag_returns_503(
    runtime_client,
    monkeypatch,
):
    client, provider = runtime_client

    monkeypatch.setenv(
        "AEGISTWIN_POSTGRES_RUNTIME_ENABLED",
        "invalid",
    )

    with patch("app.gateway.routes.SessionLocal") as session_local:
        response = client.post(
            API_PATH,
            json=request_body(),
            headers=request_headers(),
        )

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "runtime_configuration_error"
    session_local.assert_not_called()
    provider.generate.assert_not_awaited()

from fastapi import HTTPException

from app.providers.errors import ProviderError


def test_postgres_authorization_failure_returns_403(
    runtime_client,
    monkeypatch,
):
    client, provider = runtime_client
    monkeypatch.setenv(
        "AEGISTWIN_POSTGRES_RUNTIME_ENABLED", "true"
    )

    with (
        patch("app.gateway.routes.SessionLocal", mock_db_session),
        patch(
            "app.gateway.routes.generate_postgres_response",
            new_callable=AsyncMock,
            side_effect=HTTPException(
                status_code=403,
                detail={"code": "session_access_denied"},
            ),
        ),
    ):
        response = client.post(
            API_PATH,
            json=request_body(),
            headers=request_headers(str(uuid4())),
        )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "session_access_denied"
    assert "X-Aegis-Session-ID" not in response.headers
    provider.generate.assert_not_awaited()


def test_postgres_database_failure_returns_503(
    runtime_client,
    monkeypatch,
):
    client, provider = runtime_client
    monkeypatch.setenv(
        "AEGISTWIN_POSTGRES_RUNTIME_ENABLED", "true"
    )

    with (
        patch("app.gateway.routes.SessionLocal", mock_db_session),
        patch(
            "app.gateway.routes.generate_postgres_response",
            new_callable=AsyncMock,
            side_effect=RuntimeError("SECRET_DATABASE_CREDENTIAL"),
        ),
    ):
        response = client.post(
            API_PATH,
            json=request_body(),
            headers=request_headers(),
        )

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "runtime_internal_error"
    assert "SECRET_DATABASE_CREDENTIAL" not in response.text
    assert "X-Aegis-Session-ID" not in response.headers
    provider.generate.assert_not_awaited()


def test_postgres_provider_error_is_sanitized(
    runtime_client,
    monkeypatch,
):
    client, provider = runtime_client
    monkeypatch.setenv(
        "AEGISTWIN_POSTGRES_RUNTIME_ENABLED", "true"
    )

    with (
        patch("app.gateway.routes.SessionLocal", mock_db_session),
        patch(
            "app.gateway.routes.generate_postgres_response",
            new_callable=AsyncMock,
            side_effect=ProviderError(
                "SECRET_UPSTREAM_PROVIDER_KEY",
                code="provider_unavailable",
                retryable=True,
            ),
        ),
    ):
        response = client.post(
            API_PATH,
            json=request_body(),
            headers=request_headers(),
        )

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "provider_unavailable"
    assert "SECRET_UPSTREAM_PROVIDER_KEY" not in response.text
    assert "X-Aegis-Session-ID" not in response.headers
    provider.generate.assert_not_awaited()


def test_postgres_session_factory_failure_has_no_fallback(
    runtime_client,
    monkeypatch,
):
    client, provider = runtime_client
    monkeypatch.setenv(
        "AEGISTWIN_POSTGRES_RUNTIME_ENABLED", "true"
    )

    with patch(
        "app.gateway.routes.SessionLocal",
        side_effect=RuntimeError("DATABASE_UNAVAILABLE_SECRET"),
    ):
        response = client.post(
            API_PATH,
            json=request_body(),
            headers=request_headers(),
        )

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "runtime_internal_error"
    assert "DATABASE_UNAVAILABLE_SECRET" not in response.text
    provider.generate.assert_not_awaited()
