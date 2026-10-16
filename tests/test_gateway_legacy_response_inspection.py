
"""HTTP tests for legacy gateway post-LLM inspection."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.contracts import ModelResponse
from app.gateway.routes import get_provider_router
from app.main import app
from app.security.llm_response_inspector import (
    ResponseAction,
    ResponseInspection,
)


API_PATH = "/v1/model/generate"


@pytest.fixture
def gateway_client(monkeypatch):
    monkeypatch.setenv(
        "AEGISTWIN_POSTGRES_RUNTIME_ENABLED", "false"
    )
    monkeypatch.setenv(
        "AEGISTWIN_RUNTIME_API_KEY", "test-secret-key"
    )
    monkeypatch.setenv(
        "AEGISTWIN_RUNTIME_TENANT_ID", "tenant-test"
    )
    monkeypatch.setenv(
        "AEGISTWIN_RUNTIME_AGENT_ID", "agent-test"
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
            content="A safe response.",
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
        API_PATH,
        headers={"X-Aegis-API-Key": "test-secret-key"},
        json={
            "provider": "ollama",
            "model": "llama3.2:3b",
            "messages": [
                {"role": "user", "content": "Hello"}
            ],
        },
    )


def test_legacy_allow_response(gateway_client):
    client, provider = gateway_client

    response = send(client)

    assert response.status_code == 200
    assert response.json()["content"] == "A safe response."
    provider.generate.assert_awaited_once()


def test_legacy_redacts_response(gateway_client):
    client, provider = gateway_client

    async def generate(request):
        return ModelResponse(
            request_id=request.request_id,
            provider=request.provider,
            model=request.model,
            content="Contact alex@example.com for help.",
        )

    provider.generate.side_effect = generate

    response = send(client)

    assert response.status_code == 200, response.text
    assert "alex@example.com" not in response.json()["content"]
    provider.generate.assert_awaited_once()


def test_legacy_blocks_response(gateway_client):
    client, provider = gateway_client

    with patch(
        "app.gateway.routes.inspect_response",
        return_value=ResponseInspection(
            action=ResponseAction.BLOCK,
            content=None,
            reason="Test security block.",
        ),
    ):
        response = send(client)

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "response_blocked"
    assert "A safe response." not in response.text
    provider.generate.assert_awaited_once()


def test_legacy_inspector_failure_blocks_response(gateway_client):
    client, provider = gateway_client

    with patch(
        "app.gateway.routes.inspect_response",
        side_effect=RuntimeError("PRIVATE_INSPECTOR_ERROR"),
    ):
        response = send(client)

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "response_blocked"
    assert "PRIVATE_INSPECTOR_ERROR" not in response.text
    provider.generate.assert_awaited_once()


def test_postgres_does_not_run_legacy_inspector(
    gateway_client,
    monkeypatch,
):
    client, _ = gateway_client

    monkeypatch.setenv(
        "AEGISTWIN_POSTGRES_RUNTIME_ENABLED", "true"
    )

    # Verify that the legacy inspector is not invoked.
    # PostgreSQL inspection is covered by orchestrator tests.
    from app.gateway.postgres_orchestrator import OrchestrationResult
    from uuid import uuid4

    async def fake_postgres(**kwargs):
        request = kwargs["model_request"]

        return OrchestrationResult(
            response=ModelResponse(
                request_id=request.request_id,
                provider=request.provider,
                model=request.model,
                content="Already inspected.",
            ),
            session_id=str(uuid4()),
        )

    with (
        patch("app.gateway.routes.SessionLocal"),
        patch(
            "app.gateway.routes.generate_postgres_response",
            new_callable=AsyncMock,
            side_effect=fake_postgres,
        ),
        patch(
            "app.gateway.routes.inspect_response",
        ) as legacy_inspector,
    ):
        response = send(client)

    assert response.status_code == 200, response.text
    assert response.json()["content"] == "Already inspected."
    legacy_inspector.assert_not_called()
