
"""Real PostgreSQL tests for gateway request lifecycle."""

import os
from uuid import uuid4

import pytest
from sqlalchemy import delete

from app.contracts import TrustedIdentityContext
from app.gateway.postgres_request_lifecycle import (
    start_request,
    finish_request,
)
from app.gateway.postgres_session_resolver import SessionAccessDenied


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_POSTGRES_INTEGRATION") != "1",
    reason="PostgreSQL integration tests disabled.",
)


def verify_test_database():
    if os.getenv("DB_NAME") != "aegistwin_test_db":
        raise RuntimeError("Refusing non-test database.")

    from app.infrastructure.database import DATABASE_URL

    if (
        DATABASE_URL.database != "aegistwin_test_db"
        or DATABASE_URL.host not in ("localhost", "127.0.0.1")
        or DATABASE_URL.port not in (55432, 55433)
    ):
        raise RuntimeError("Unsafe database connection.")


def identity(tenant_id, agent_id, session_id):
    return TrustedIdentityContext(
        tenant_id=str(tenant_id),
        agent_id=str(agent_id),
        session_id=str(session_id),
        user_id="test-user",
    )


@pytest.fixture
def records():
    verify_test_database()

    from app.infrastructure.database import SessionLocal
    from app.infrastructure.models import (
        Tenant,
        Agent,
        AgentSession,
        AgentRequest,
    )

    tenant_ids = []
    agent_ids = []
    session_ids = []

    try:
        with SessionLocal() as db:
            tenant_a = Tenant(name=f"Lifecycle A {uuid4().hex}")
            tenant_b = Tenant(name=f"Lifecycle B {uuid4().hex}")

            db.add_all([tenant_a, tenant_b])
            db.flush()

            tenant_ids = [tenant_a.id, tenant_b.id]

            agent_a = Agent(
                tenant_id=tenant_a.id,
                name="Lifecycle Agent A",
            )
            agent_b = Agent(
                tenant_id=tenant_b.id,
                name="Lifecycle Agent B",
            )

            db.add_all([agent_a, agent_b])
            db.flush()

            agent_ids = [agent_a.id, agent_b.id]

            session_a = AgentSession(
                tenant_id=tenant_a.id,
                agent_id=agent_a.id,
            )

            db.add(session_a)
            db.flush()
            session_ids = [session_a.id]

            data = {
                "tenant_a": tenant_a.id,
                "tenant_b": tenant_b.id,
                "agent_a": agent_a.id,
                "agent_b": agent_b.id,
                "session_a": session_a.id,
            }

            db.commit()

        yield data

    finally:
        # Remove all test records in dependency order.
        # Cleanup runs even if assertions fail.
        with SessionLocal() as db:
            try:
                if tenant_ids:
                    db.execute(
                        delete(AgentRequest).where(
                            AgentRequest.tenant_id.in_(tenant_ids)
                        )
                    )

                if session_ids:
                    db.execute(
                        delete(AgentSession).where(
                            AgentSession.id.in_(session_ids)
                        )
                    )

                if agent_ids:
                    db.execute(
                        delete(Agent).where(
                            Agent.id.in_(agent_ids)
                        )
                    )

                if tenant_ids:
                    db.execute(
                        delete(Tenant).where(
                            Tenant.id.in_(tenant_ids)
                        )
                    )

                db.commit()
            except Exception:
                db.rollback()
                raise


def create_pending(data):
    from app.infrastructure.database import SessionLocal

    with SessionLocal() as db:
        request = start_request(
            identity=identity(
                data["tenant_a"],
                data["agent_a"],
                data["session_a"],
            ),
            public_request_id=f"REQ-{uuid4().hex[:12]}",
            provider="ollama",
            model="llama3.2:3b",
            db=db,
        )

        # Commit the pending record before completion.
        db.commit()

        return request


def test_request_creation(records):
    from app.infrastructure.persistence import get_request

    request = create_pending(records)

    saved = get_request(
        request_id=request.request_id,
        tenant_id=records["tenant_a"],
    )

    assert saved is not None
    assert saved["status"] == "pending"
    assert saved["provider"] == "ollama"
    assert saved["model"] == "llama3.2:3b"


def test_successful_completion(records):
    from app.infrastructure.persistence import get_request

    request = create_pending(records)

    finish_request(
        request=request,
        outcome="completed",
        latency_ms=125.5,
        input_tokens=35,
        output_tokens=48,
    )

    saved = get_request(
        request.request_id,
        records["tenant_a"],
    )

    assert saved["status"] == "completed"
    assert saved["latency"] == pytest.approx(125.5)
    assert saved["input_tokens"] == 35
    assert saved["output_tokens"] == 48


def test_provider_failure(records):
    from app.infrastructure.persistence import get_request

    request = create_pending(records)

    finish_request(
        request=request,
        outcome="failed",
        error_code="provider_unavailable",
    )

    saved = get_request(
        request.request_id,
        records["tenant_a"],
    )

    assert saved["status"] == "failed"
    assert saved["error_code"] == "provider_unavailable"


def test_blocked_response(records):
    from app.infrastructure.persistence import get_request

    request = create_pending(records)

    finish_request(
        request=request,
        outcome="blocked",
    )

    saved = get_request(
        request.request_id,
        records["tenant_a"],
    )

    assert saved["status"] == "blocked"
    assert saved["error_code"] == "response_blocked"


def test_foreign_session_cannot_create_request(records):
    from app.infrastructure.database import SessionLocal
    from app.infrastructure.models import AgentRequest

    with SessionLocal() as db:
        before = db.query(AgentRequest).filter(
            AgentRequest.tenant_id == records["tenant_b"]
        ).count()

        with pytest.raises(SessionAccessDenied):
            start_request(
                identity=identity(
                    records["tenant_b"],
                    records["agent_b"],
                    records["session_a"],
                ),
                public_request_id=f"REQ-{uuid4().hex[:12]}",
                provider="ollama",
                model="llama3.2:3b",
                db=db,
            )

        after = db.query(AgentRequest).filter(
            AgentRequest.tenant_id == records["tenant_b"]
        ).count()

        assert after == before
