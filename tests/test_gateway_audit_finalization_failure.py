
"""Gateway tests for PostgreSQL audit-finalization failures."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.contracts import ModelResponse
from app.gateway.routes import get_provider_router
from app.gateway.postgres_session_manager import ManagedSession
from app.main import app


API_PATH = "/v1/model/generate"

SECRET_RESPONSE = "PRIVATE-MODEL-OUTPUT-DO-NOT-RELEASE"
SECRET_DATABASE_ERROR = "PRIVATE-DB-CREDENTIALS-DO-NOT-RELEASE"


@pytest.fixture
def runtime_client(monkeypatch):
    """Create an authenticated, PostgreSQL-enabled test client."""

    monkeypatch.setenv(
        "AEGISTWIN_POSTGRES_RUNTIME_ENABLED", "true"
    )
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
            content=SECRET_RESPONSE,
            usage={
                "input_tokens": 5,
                "output_tokens": 7,
            },
            latency_ms=10.5,
        )

    provider.generate = AsyncMock(side_effect=generate)

    app.dependency_overrides[get_provider_router] = (
        lambda: provider
    )

    try:
        with TestClient(app) as client:
            yield client, provider
    finally:
        app.dependency_overrides.pop(
            get_provider_router, None
        )


def send_request(client):
    return client.post(
        API_PATH,
        headers={
            "X-Aegis-API-Key": "test-secret-key"
        },
        json={
            "provider": "ollama",
            "model": "llama3.2:3b",
            "messages": [
                {
                    "role": "user",
                    "content": "Hello",
                }
            ],
        },
    )


def test_finalization_database_failure_returns_safe_503(
    runtime_client,
):
    """Successful inference cannot bypass failed audit finalization."""

    client, provider = runtime_client

    db = MagicMock()
    session_id = uuid4()

    def manage_session(*, identity, db, requested_session_id):
        return ManagedSession(
            identity=identity.model_copy(
                update={"session_id": str(session_id)}
            ),
            session_id=session_id,
            created=True,
        )

    database_error = OperationalError(
        "UPDATE requests SET status='completed'",
        {},
        Exception(SECRET_DATABASE_ERROR),
    )

    with (
        patch(
            "app.gateway.routes.SessionLocal"
        ) as session_local,
        patch(
            "app.gateway.postgres_orchestrator."
            "manage_postgres_session",
            side_effect=manage_session,
        ),
        patch(
            "app.gateway.postgres_orchestrator."
            "start_request",
            return_value=MagicMock(),
        ),
        patch(
            "app.gateway.postgres_orchestrator."
            "finish_request",
            side_effect=database_error,
        ) as finish,
        patch(
            "app.gateway.postgres_orchestrator."
            "inspect_response",
        ) as inspector,
    ):
        session_local.return_value.__enter__.return_value = db

        from app.security.llm_response_inspector import (
            ResponseAction,
            ResponseInspection,
        )

        inspector.return_value = ResponseInspection(
            action=ResponseAction.ALLOW,
            content=SECRET_RESPONSE,
            reason="Safe response.",
        )

        response = send_request(client)

    assert response.status_code == 503

    detail = response.json()["detail"]

    assert detail["code"] == "database_unavailable"
    assert detail["message"] == (
        "The runtime database is unavailable."
    )
    assert detail["request_id"].startswith("REQ-")

    assert SECRET_RESPONSE not in response.text
    assert SECRET_DATABASE_ERROR not in response.text
    assert "UPDATE requests" not in response.text

    provider.generate.assert_awaited_once()
    finish.assert_called_once()
    assert finish.call_args.kwargs["outcome"] == "completed"

    # Pending audit was committed before inference.
    db.commit.assert_called_once()


def test_unexpected_finalization_error_returns_safe_503(
    runtime_client,
):
    """Unexpected persistence errors must not leak internal details."""

    client, provider = runtime_client

    db = MagicMock()
    session_id = uuid4()

    def manage_session(*, identity, db, requested_session_id):
        return ManagedSession(
            identity=identity.model_copy(
                update={"session_id": str(session_id)}
            ),
            session_id=session_id,
            created=True,
        )

    with (
        patch(
            "app.gateway.routes.SessionLocal"
        ) as session_local,
        patch(
            "app.gateway.postgres_orchestrator."
            "manage_postgres_session",
            side_effect=manage_session,
        ),
        patch(
            "app.gateway.postgres_orchestrator."
            "start_request",
            return_value=MagicMock(),
        ),
        patch(
            "app.gateway.postgres_orchestrator."
            "finish_request",
            side_effect=RuntimeError(SECRET_DATABASE_ERROR),
        ) as finish,
        patch(
            "app.gateway.postgres_orchestrator."
            "inspect_response",
        ) as inspector,
    ):
        session_local.return_value.__enter__.return_value = db

        from app.security.llm_response_inspector import (
            ResponseAction,
            ResponseInspection,
        )

        inspector.return_value = ResponseInspection(
            action=ResponseAction.ALLOW,
            content=SECRET_RESPONSE,
            reason="Safe response.",
        )

        response = send_request(client)

    assert response.status_code == 503

    detail = response.json()["detail"]

    assert detail["code"] == "runtime_internal_error"
    assert detail["request_id"].startswith("REQ-")

    assert SECRET_RESPONSE not in response.text
    assert SECRET_DATABASE_ERROR not in response.text

    provider.generate.assert_awaited_once()
    finish.assert_called_once()
    db.commit.assert_called_once()
