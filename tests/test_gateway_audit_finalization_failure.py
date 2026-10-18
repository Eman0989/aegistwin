
"""Gateway tests for PostgreSQL audit-finalization failures."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.contracts import ModelResponse
from app.gateway.routes import get_provider_router
from app.gateway.postgres_request_lifecycle import PersistedRequest
from app.gateway.postgres_session_manager import ManagedSession
from app.main import app
from app.security.llm_response_inspector import (
    ResponseAction,
    ResponseInspection,
)


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


def make_persisted_request(session_id):
    """Return a request whose lease was created atomically."""

    return PersistedRequest(
        request_id=uuid4(),
        tenant_id=uuid4(),
        agent_id=uuid4(),
        session_id=session_id,
        public_request_id="REQ-test123",
        lease_token="test-audit-lease-token",
    )


def manage_test_session(
    *,
    identity,
    db,
    requested_session_id,
    session_id,
):
    return ManagedSession(
        identity=identity.model_copy(
            update={"session_id": str(session_id)}
        ),
        session_id=session_id,
        created=True,
    )


# ==========================================================
# TEST 1 — DATABASE FAILURE DURING FINALIZATION
# ==========================================================


def test_finalization_database_failure_returns_safe_503(
    runtime_client,
):
    """Successful inference cannot bypass failed audit finalization."""

    client, provider = runtime_client

    db = MagicMock()
    session_id = uuid4()
    persisted = make_persisted_request(session_id)

    def manage_session(*, identity, db, requested_session_id):
        return manage_test_session(
            identity=identity,
            db=db,
            requested_session_id=requested_session_id,
            session_id=session_id,
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
            "start_leased_request",
            return_value=persisted,
        ) as starter,
        patch(
            "app.gateway.postgres_orchestrator."
            "finish_request",
            side_effect=database_error,
        ) as finish,
        patch(
            "app.gateway.postgres_orchestrator."
            "inspect_response",
            return_value=ResponseInspection(
                action=ResponseAction.ALLOW,
                content=SECRET_RESPONSE,
                reason="Safe response.",
            ),
        ),
    ):
        session_local.return_value.__enter__.return_value = db

        response = send_request(client)

    assert response.status_code == 503

    detail = response.json()["detail"]

    assert detail["code"] == "database_unavailable"
    assert detail["message"] == (
        "The runtime database is unavailable."
    )
    assert detail["request_id"].startswith("REQ-")

    # Neither generated content nor internal database
    # details may appear in the HTTP response.
    assert SECRET_RESPONSE not in response.text
    assert SECRET_DATABASE_ERROR not in response.text
    assert "UPDATE requests" not in response.text

    # Inference occurred before audit finalization failed.
    provider.generate.assert_awaited_once()

    # Request creation and initial lease assignment
    # are now performed by the same operation.
    starter.assert_called_once()
    assert (
        starter.call_args.kwargs["lease_seconds"]
        == 60
    )
    assert (
        starter.call_args.kwargs["worker_id"]
        .startswith("aegis-worker-")
    )

    # Finalization was attempted but its failure
    # prevented the generated output from reaching
    # the client.
    finish.assert_called_once()
    assert finish.call_args.kwargs["outcome"] == "completed"

    finalized_request = finish.call_args.kwargs["request"]

    assert (
        finalized_request.lease_token
        == "test-audit-lease-token"
    )
    assert finalized_request.request_id == persisted.request_id

    # One commit makes the request and lease durable
    # before inference begins.
    db.commit.assert_called_once()
    db.rollback.assert_not_called()


# ==========================================================
# TEST 2 — UNEXPECTED FAILURE DURING FINALIZATION
# ==========================================================


def test_unexpected_finalization_error_returns_safe_503(
    runtime_client,
):
    """Unexpected persistence errors must not leak internal details."""

    client, provider = runtime_client

    db = MagicMock()
    session_id = uuid4()
    persisted = make_persisted_request(session_id)

    def manage_session(*, identity, db, requested_session_id):
        return manage_test_session(
            identity=identity,
            db=db,
            requested_session_id=requested_session_id,
            session_id=session_id,
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
            "start_leased_request",
            return_value=persisted,
        ) as starter,
        patch(
            "app.gateway.postgres_orchestrator."
            "finish_request",
            side_effect=RuntimeError(
                SECRET_DATABASE_ERROR
            ),
        ) as finish,
        patch(
            "app.gateway.postgres_orchestrator."
            "inspect_response",
            return_value=ResponseInspection(
                action=ResponseAction.ALLOW,
                content=SECRET_RESPONSE,
                reason="Safe response.",
            ),
        ),
    ):
        session_local.return_value.__enter__.return_value = db

        response = send_request(client)

    assert response.status_code == 503

    detail = response.json()["detail"]

    assert detail["code"] == "runtime_internal_error"
    assert detail["request_id"].startswith("REQ-")

    assert SECRET_RESPONSE not in response.text
    assert SECRET_DATABASE_ERROR not in response.text

    provider.generate.assert_awaited_once()

    starter.assert_called_once()
    assert starter.call_args.kwargs["lease_seconds"] == 60

    finish.assert_called_once()
    assert finish.call_args.kwargs["outcome"] == "completed"

    assert (
        finish.call_args.kwargs["request"].lease_token
        == "test-audit-lease-token"
    )

    db.commit.assert_called_once()
    db.rollback.assert_not_called()
