
"""HTTP request correlation tests for AegisTwin."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.contracts import ModelResponse
from app.gateway.routes import get_provider_router
from app.gateway.postgres_orchestrator import OrchestrationResult
from app.main import app


PATH = "/v1/model/generate"


@pytest.fixture
def client_and_provider(monkeypatch):
    monkeypatch.setenv(
        "AEGISTWIN_RUNTIME_API_KEY", "test-secret-key"
    )
    monkeypatch.setenv(
        "AEGISTWIN_RUNTIME_TENANT_ID", str(uuid4())
    )
    monkeypatch.setenv(
        "AEGISTWIN_RUNTIME_AGENT_ID", str(uuid4())
    )
    monkeypatch.setenv(
        "AEGISTWIN_RUNTIME_USER_ID", "test-user"
    )

    provider = MagicMock()

    async def generate(request):
        return ModelResponse(
            request_id=request.request_id,
            provider=request.provider,
            model=request.model,
            content="Safe response.",
        )

    provider.generate = AsyncMock(side_effect=generate)
    app.dependency_overrides[get_provider_router] = lambda: provider

    try:
        with TestClient(app) as client:
            yield client, provider
    finally:
        app.dependency_overrides.pop(get_provider_router, None)


def send(client):
    return client.post(
        PATH,
        headers={"X-Aegis-API-Key": "test-secret-key"},
        json={
            "provider": "ollama",
            "model": "llama3.2:3b",
            "messages": [
                {"role": "user", "content": "Hello"}
            ],
        },
    )


def assert_matching_error_id(response):
    header_id = response.headers["X-Request-ID"]
    body_id = response.json()["detail"]["request_id"]

    assert header_id.startswith("REQ-")
    assert header_id == body_id


def test_legacy_success_request_id(client_and_provider, monkeypatch):
    client, _ = client_and_provider
    monkeypatch.setenv(
        "AEGISTWIN_POSTGRES_RUNTIME_ENABLED", "false"
    )

    response = send(client)

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == (
        response.json()["request_id"]
    )


def test_legacy_block_request_id(client_and_provider, monkeypatch):
    client, provider = client_and_provider
    monkeypatch.setenv(
        "AEGISTWIN_POSTGRES_RUNTIME_ENABLED", "false"
    )

    async def generate(request):
        return ModelResponse(
            request_id=request.request_id,
            provider=request.provider,
            model=request.model,
            content="Contact alice@example.com",
        )

    provider.generate.side_effect = generate

    from app.security.llm_response_inspector import (
        ResponseAction,
        ResponseInspection,
    )

    with patch(
        "app.gateway.routes.inspect_response",
        return_value=ResponseInspection(
            action=ResponseAction.BLOCK,
            content=None,
            reason="Blocked for test.",
        ),
    ):
        response = send(client)

    assert response.status_code == 403
    assert_matching_error_id(response)


def test_invalid_runtime_flag_request_id(
    client_and_provider, monkeypatch
):
    client, _ = client_and_provider
    monkeypatch.setenv(
        "AEGISTWIN_POSTGRES_RUNTIME_ENABLED", "invalid"
    )

    response = send(client)

    assert response.status_code == 503
    assert_matching_error_id(response)


def test_postgres_success_request_id(
    client_and_provider, monkeypatch
):
    client, _ = client_and_provider
    monkeypatch.setenv(
        "AEGISTWIN_POSTGRES_RUNTIME_ENABLED", "true"
    )

    session_id = str(uuid4())

    async def generate_postgres(**kwargs):
        request = kwargs["model_request"]

        return OrchestrationResult(
            response=ModelResponse(
                request_id=request.request_id,
                provider=request.provider,
                model=request.model,
                content="Inspected response.",
            ),
            session_id=session_id,
        )

    with (
        patch("app.gateway.routes.SessionLocal"),
        patch(
            "app.gateway.routes.generate_postgres_response",
            new_callable=AsyncMock,
            side_effect=generate_postgres,
        ),
    ):
        response = send(client)

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == (
        response.json()["request_id"]
    )
    assert response.headers["X-Aegis-Session-ID"] == session_id


def test_postgres_database_failure_request_id(
    client_and_provider, monkeypatch
):
    client, _ = client_and_provider
    monkeypatch.setenv(
        "AEGISTWIN_POSTGRES_RUNTIME_ENABLED", "true"
    )

    from fastapi import HTTPException

    async def fail_postgres(**kwargs):
        request_id = kwargs["model_request"].request_id

        raise HTTPException(
            status_code=503,
            detail={
                "code": "database_unavailable",
                "message": "The runtime database is unavailable.",
                "request_id": request_id,
            },
        )

    with (
        patch("app.gateway.routes.SessionLocal"),
        patch(
            "app.gateway.routes.generate_postgres_response",
            new_callable=AsyncMock,
            side_effect=fail_postgres,
        ),
    ):
        response = send(client)

    assert response.status_code == 503
    assert_matching_error_id(response)
