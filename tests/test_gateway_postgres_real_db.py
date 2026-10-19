
"""Real PostgreSQL HTTP tests for AegisTwin's gateway."""

import os
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.main import app
from app.contracts import ModelResponse
from app.gateway.routes import get_provider_router
from app.providers.errors import ProviderError


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_POSTGRES_INTEGRATION") != "1",
    reason="Real PostgreSQL integration tests disabled.",
)

API_PATH = "/v1/model/generate"


# ==================================================
# DATABASE SAFETY
# ==================================================

def verify_test_database():
    """Never run destructive tests against a non-test database."""

    if os.getenv("DB_NAME") != "aegistwin_test_db":
        raise RuntimeError("Refusing non-test database.")

    from app.infrastructure.database import DATABASE_URL

    if (
        DATABASE_URL.database != "aegistwin_test_db"
        or DATABASE_URL.host not in ("localhost", "127.0.0.1")
        or DATABASE_URL.port not in (55432, 55433)
    ):
        raise RuntimeError("Unsafe database connection.")


# ==================================================
# TEMPORARY POSTGRESQL TEST RECORDS
# ==================================================

@pytest.fixture
def records(monkeypatch):
    """Create isolated tenants and clean up committed records."""

    verify_test_database()

    from app.infrastructure.database import SessionLocal
    from app.infrastructure.models import (
        Tenant,
        Agent,
        AgentSession,
        AgentRequest,
    )

    tenant_ids = []

    try:
        with SessionLocal() as db:
            tenant_a = Tenant(name=f"HTTP Test A {uuid4().hex}")
            tenant_b = Tenant(name=f"HTTP Test B {uuid4().hex}")

            db.add_all([tenant_a, tenant_b])
            db.flush()

            tenant_ids = [tenant_a.id, tenant_b.id]

            agent_a = Agent(
                tenant_id=tenant_a.id,
                name="HTTP Agent A",
            )

            agent_b = Agent(
                tenant_id=tenant_a.id,
                name="HTTP Agent B",
            )

            foreign_agent = Agent(
                tenant_id=tenant_b.id,
                name="HTTP Foreign Agent",
            )

            db.add_all(
                [agent_a, agent_b, foreign_agent]
            )
            db.flush()

            data = {
                "tenant_a": tenant_a.id,
                "tenant_b": tenant_b.id,
                "agent_a": agent_a.id,
                "agent_b": agent_b.id,
                "foreign_agent": foreign_agent.id,
            }

            db.commit()

        monkeypatch.setenv(
            "AEGISTWIN_POSTGRES_RUNTIME_ENABLED",
            "true",
        )
        monkeypatch.setenv(
            "AEGISTWIN_RUNTIME_API_KEY",
            "http-db-test-key",
        )
        monkeypatch.setenv(
            "AEGISTWIN_RUNTIME_TENANT_ID",
            str(data["tenant_a"]),
        )
        monkeypatch.setenv(
            "AEGISTWIN_RUNTIME_AGENT_ID",
            str(data["agent_a"]),
        )
        monkeypatch.setenv(
            "AEGISTWIN_RUNTIME_USER_ID",
            "http-test-user",
        )

        yield data

    finally:
        # Delete all data owned by the temporary tenants
        # in foreign-key dependency order.
        if tenant_ids:
            with SessionLocal() as db:
                try:
                    db.execute(
                        delete(AgentRequest).where(
                            AgentRequest.tenant_id.in_(
                                tenant_ids
                            )
                        )
                    )

                    db.execute(
                        delete(AgentSession).where(
                            AgentSession.tenant_id.in_(
                                tenant_ids
                            )
                        )
                    )

                    db.execute(
                        delete(Agent).where(
                            Agent.tenant_id.in_(
                                tenant_ids
                            )
                        )
                    )

                    db.execute(
                        delete(Tenant).where(
                            Tenant.id.in_(
                                tenant_ids
                            )
                        )
                    )

                    db.commit()

                except Exception:
                    db.rollback()
                    raise


# ==================================================
# MOCKED PROVIDER / REAL DATABASE / REAL HTTP
# ==================================================

@pytest.fixture
def gateway_client(records):
    """Use a mocked LLM with real FastAPI and PostgreSQL."""

    provider = MagicMock()

    async def generate(model_request):
        return ModelResponse(
            request_id=model_request.request_id,
            provider=model_request.provider,
            model=model_request.model,
            content="Safe response from test provider.",
            usage={
                "input_tokens": 10,
                "output_tokens": 7,
            },
            latency_ms=12.5,
        )

    provider.generate = AsyncMock(
        side_effect=generate
    )

    app.dependency_overrides[
        get_provider_router
    ] = lambda: provider

    try:
        with TestClient(app) as client:
            yield client, provider

    finally:
        app.dependency_overrides.pop(
            get_provider_router,
            None,
        )


# ==================================================
# HTTP REQUEST HELPERS
# ==================================================

def headers(session_id=None):
    result = {
        "X-Aegis-API-Key": "http-db-test-key"
    }

    if session_id is not None:
        result["X-Aegis-Session-ID"] = str(
            session_id
        )

    return result


def body():
    return {
        "provider": "ollama",
        "model": "llama3.2:3b",
        "messages": [
            {
                "role": "user",
                "content": "Hello",
            }
        ],
    }


def send(client, session_id=None):
    return client.post(
        API_PATH,
        json=body(),
        headers=headers(session_id),
    )


# ==================================================
# 1. SESSION CREATION AND COMPLETED AUDIT
# ==================================================

def test_http_creates_session_and_completed_audit(
    records,
    gateway_client,
):
    from app.infrastructure.database import SessionLocal
    from app.infrastructure.models import (
        AgentRequest,
        AgentSession,
    )

    client, provider = gateway_client

    response = send(client)

    assert response.status_code == 200, response.text

    assert response.json()["content"] == (
        "Safe response from test provider."
    )

    session_id = UUID(
        response.headers["X-Aegis-Session-ID"]
    )

    with SessionLocal() as db:
        session = db.get(
            AgentSession,
            session_id,
        )

        assert session is not None
        assert session.tenant_id == records["tenant_a"]
        assert session.agent_id == records["agent_a"]

        audits = db.execute(
            select(AgentRequest).where(
                AgentRequest.tenant_id
                == records["tenant_a"],
                AgentRequest.session_id
                == session_id,
            )
        ).scalars().all()

        assert len(audits) == 1

        audit = audits[0]

        assert audit.status == "completed"
        assert audit.completed_at is not None
        assert audit.provider == "ollama"
        assert audit.model == "llama3.2:3b"
        assert audit.input_tokens == 10
        assert audit.output_tokens == 7

    provider.generate.assert_awaited_once()


# ==================================================
# 2. REUSE EXISTING POSTGRESQL SESSION
# ==================================================

def test_http_reuses_existing_session(
    records,
    gateway_client,
):
    from app.infrastructure.database import SessionLocal
    from app.infrastructure.models import (
        AgentRequest,
        AgentSession,
    )

    client, provider = gateway_client

    first = send(client)

    assert first.status_code == 200, first.text

    session_id = first.headers[
        "X-Aegis-Session-ID"
    ]

    second = send(
        client,
        session_id,
    )

    assert second.status_code == 200, second.text

    assert (
        second.headers["X-Aegis-Session-ID"]
        == session_id
    )

    with SessionLocal() as db:
        sessions = db.execute(
            select(AgentSession).where(
                AgentSession.tenant_id
                == records["tenant_a"]
            )
        ).scalars().all()

        audits = db.execute(
            select(AgentRequest).where(
                AgentRequest.tenant_id
                == records["tenant_a"]
            )
        ).scalars().all()

        assert len(sessions) == 1
        assert len(audits) == 2

        assert all(
            audit.status == "completed"
            for audit in audits
        )

    assert provider.generate.await_count == 2


# ==================================================
# 3. FOREIGN TENANT CANNOT REUSE SESSION
# ==================================================

def test_http_rejects_foreign_tenant_session(
    records,
    gateway_client,
    monkeypatch,
):
    client, provider = gateway_client

    first = send(client)

    assert first.status_code == 200, first.text

    session_id = first.headers[
        "X-Aegis-Session-ID"
    ]

    monkeypatch.setenv(
        "AEGISTWIN_RUNTIME_TENANT_ID",
        str(records["tenant_b"]),
    )

    monkeypatch.setenv(
        "AEGISTWIN_RUNTIME_AGENT_ID",
        str(records["foreign_agent"]),
    )

    second = send(
        client,
        session_id,
    )

    assert second.status_code == 403

    assert second.json()["detail"]["code"] == (
        "session_access_denied"
    )

    assert provider.generate.await_count == 1

    assert (
        "X-Aegis-Session-ID"
        not in second.headers
    )


# ==================================================
# 4. DIFFERENT AGENT CANNOT REUSE SESSION
# ==================================================

def test_http_rejects_foreign_agent_session(
    records,
    gateway_client,
    monkeypatch,
):
    client, provider = gateway_client

    first = send(client)

    assert first.status_code == 200, first.text

    session_id = first.headers[
        "X-Aegis-Session-ID"
    ]

    # Same tenant, different agent.
    monkeypatch.setenv(
        "AEGISTWIN_RUNTIME_AGENT_ID",
        str(records["agent_b"]),
    )

    second = send(
        client,
        session_id,
    )

    assert second.status_code == 403

    assert second.json()["detail"]["code"] == (
        "session_access_denied"
    )

    assert provider.generate.await_count == 1

    assert (
        "X-Aegis-Session-ID"
        not in second.headers
    )


# ==================================================
# 5. BLOCKED RESPONSE IS AUDITED
# ==================================================

def test_http_blocked_response_is_audited(
    records,
    gateway_client,
    monkeypatch,
):
    from app.infrastructure.database import SessionLocal
    from app.infrastructure.models import AgentRequest
    from app.security.llm_response_inspector import (
        ResponseAction,
    )

    client, provider = gateway_client

    # Reuse the real inspector's result type so this test
    # does not depend on a guessed class constructor.
    from app.security.llm_response_inspector import (
        inspect_response,
    )

    sample_result = inspect_response(
        "Safe test content"
    )

    def blocked_inspection(content):
        return type(sample_result)(
            action=ResponseAction.BLOCK,
            content=content,
            reasons=["Test security policy"],
        )

    monkeypatch.setattr(
        "app.gateway.postgres_orchestrator.inspect_response",
        blocked_inspection,
    )

    response = send(client)

    assert response.status_code == 403

    assert response.json()["detail"]["code"] == (
        "response_blocked"
    )

    assert (
        "X-Aegis-Session-ID"
        not in response.headers
    )

    with SessionLocal() as db:
        audits = db.execute(
            select(AgentRequest).where(
                AgentRequest.tenant_id
                == records["tenant_a"]
            )
        ).scalars().all()

        assert len(audits) == 1

        assert audits[0].status == "blocked"
        assert audits[0].completed_at is not None

    provider.generate.assert_awaited_once()


# ==================================================
# 6. PROVIDER FAILURE IS AUDITED
# ==================================================

def test_http_provider_failure_is_audited(
    records,
    gateway_client,
):
    from app.infrastructure.database import SessionLocal
    from app.infrastructure.models import AgentRequest

    client, provider = gateway_client

    provider.generate.side_effect = ProviderError(
        "PRIVATE_PROVIDER_TOKEN",
        code="provider_unavailable",
        retryable=True,
    )

    response = send(client)

    assert response.status_code == 503

    assert response.json()["detail"]["code"] == (
        "provider_unavailable"
    )

    assert (
        "PRIVATE_PROVIDER_TOKEN"
        not in response.text
    )

    assert (
        "X-Aegis-Session-ID"
        not in response.headers
    )

    with SessionLocal() as db:
        audits = db.execute(
            select(AgentRequest).where(
                AgentRequest.tenant_id
                == records["tenant_a"]
            )
        ).scalars().all()

        assert len(audits) == 1

        assert audits[0].status == "failed"

        assert audits[0].error_code == (
            "provider_unavailable"
        )

        assert audits[0].completed_at is not None

# ==================================================
# 7. REAL OLLAMA + HTTP + POSTGRESQL END-TO-END TEST
# ==================================================

@pytest.mark.skipif(
    os.getenv("RUN_LIVE_OLLAMA_TESTS") != "1",
    reason="Live Ollama testing is disabled.",
)
def test_real_ollama_request_is_persisted(records):
    """Verify real LLM inference through HTTP and PostgreSQL."""

    from app.infrastructure.database import SessionLocal
    from app.infrastructure.models import AgentRequest, AgentSession

    # Never run this test against the application database.
    verify_test_database()

    # Use the real commercial provider adapter, not a mock.
    assert get_provider_router not in app.dependency_overrides

    with TestClient(app) as client:
        response = client.post(
            API_PATH,
            headers=headers(),
            json={
                "provider": "ollama",
                "model": "llama3.2:3b",
                "messages": [
                    {
                        "role": "user",
                        "content": (
                            "Reply briefly with: "
                            "AegisTwin integration successful"
                        ),
                    }
                ],
            },
        )

    assert response.status_code == 200, response.text

    payload = response.json()

    assert payload["content"].strip()
    assert payload["provider"] == "ollama"
    assert payload["model"] == "llama3.2:3b"

    session_id = UUID(
        response.headers["X-Aegis-Session-ID"]
    )

    with SessionLocal() as db:
        session = db.get(AgentSession, session_id)

        assert session is not None
        assert session.tenant_id == records["tenant_a"]
        assert session.agent_id == records["agent_a"]

        audits = db.execute(
            select(AgentRequest).where(
                AgentRequest.tenant_id == records["tenant_a"],
                AgentRequest.session_id == session_id,
            )
        ).scalars().all()

        assert len(audits) == 1

        audit = audits[0]

        assert audit.status == "completed"
        assert audit.completed_at is not None
        assert audit.provider == "ollama"
        assert audit.model == "llama3.2:3b"
        assert audit.agent_id == records["agent_a"]
        assert audit.input_tokens is not None
        assert audit.input_tokens > 0
        assert audit.output_tokens is not None
        assert audit.output_tokens > 0

    print("Real Ollama inference: SUCCESS")
    print("Authenticated gateway: SUCCESS")
    print("PostgreSQL audit: SUCCESS")
