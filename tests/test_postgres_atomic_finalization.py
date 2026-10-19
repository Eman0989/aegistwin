
"""Real PostgreSQL tests for atomic request finalization."""

import os
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from sqlalchemy import delete

from app.infrastructure.database import DATABASE_URL, SessionLocal
from app.infrastructure.models import (
    Agent,
    AgentRequest,
    AgentSession,
    Tenant,
)
from app.infrastructure.persistence import (
    complete_request,
    create_request,
)


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_POSTGRES_INTEGRATION") != "1",
    reason="PostgreSQL integration tests disabled.",
)


@pytest.fixture
def records():
    if (
        os.getenv("DB_NAME") != "aegistwin_test_db"
        or DATABASE_URL.database != "aegistwin_test_db"
        or DATABASE_URL.host not in ("localhost", "127.0.0.1")
        or DATABASE_URL.port not in (55432, 55433)
    ):
        raise RuntimeError("Unsafe test database.")

    tenant_ids = []
    agent_ids = []
    session_ids = []

    try:
        with SessionLocal() as db:
            tenant_a = Tenant(name=f"Atomic-A-{uuid4().hex}")
            tenant_b = Tenant(name=f"Atomic-B-{uuid4().hex}")
            db.add_all([tenant_a, tenant_b])
            db.flush()
            tenant_ids = [tenant_a.id, tenant_b.id]

            agent_a = Agent(
                tenant_id=tenant_a.id,
                name="Atomic Agent A",
            )
            agent_b = Agent(
                tenant_id=tenant_b.id,
                name="Atomic Agent B",
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
                "session_a": session_a.id,
            }
            db.commit()

        yield data

    finally:
        with SessionLocal() as db:
            db.execute(
                delete(AgentRequest).where(
                    AgentRequest.tenant_id.in_(tenant_ids)
                )
            )
            db.execute(
                delete(AgentSession).where(
                    AgentSession.id.in_(session_ids)
                )
            )
            db.execute(
                delete(Agent).where(
                    Agent.id.in_(agent_ids)
                )
            )
            db.execute(
                delete(Tenant).where(
                    Tenant.id.in_(tenant_ids)
                )
            )
            db.commit()


def pending_request(records):
    return create_request(
        tenant_id=records["tenant_a"],
        agent_id=records["agent_a"],
        session_id=records["session_a"],
        provider="test",
        model="test-model",
        public_request_id=f"REQ-{uuid4().hex[:12]}",
    )


def test_pending_request_can_finalize(records):
    request_id = pending_request(records)

    result = complete_request(
        request_id,
        records["tenant_a"],
        "completed",
        latency=123.0,
    )

    assert result == request_id

    with SessionLocal() as db:
        saved = db.get(AgentRequest, request_id)
        assert saved.status == "completed"
        assert saved.latency == 123.0
        assert saved.completed_at is not None


def test_completed_request_cannot_be_overwritten(records):
    request_id = pending_request(records)

    assert complete_request(
        request_id,
        records["tenant_a"],
        "completed",
    ) == request_id

    result = complete_request(
        request_id,
        records["tenant_a"],
        "failed",
        error_code="provider_error",
    )

    assert result is None

    with SessionLocal() as db:
        saved = db.get(AgentRequest, request_id)
        assert saved.status == "completed"
        assert saved.error_code is None


def test_foreign_tenant_cannot_finalize(records):
    request_id = pending_request(records)

    result = complete_request(
        request_id,
        records["tenant_b"],
        "completed",
    )

    assert result is None

    with SessionLocal() as db:
        saved = db.get(AgentRequest, request_id)
        assert saved.status == "pending"


def test_recovered_request_cannot_be_overwritten(records):
    request_id = pending_request(records)

    # Simulate a future recovery operation.
    with SessionLocal() as db:
        saved = db.get(AgentRequest, request_id)
        saved.status = "recovered"
        db.commit()

    result = complete_request(
        request_id,
        records["tenant_a"],
        "completed",
    )

    assert result is None


def test_concurrent_workers_only_one_finalizes(records):
    request_id = pending_request(records)

    def finalize(outcome):
        return complete_request(
            request_id,
            records["tenant_a"],
            outcome,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(finalize, "completed"),
            executor.submit(finalize, "failed"),
        ]
        results = [future.result() for future in futures]

    assert results.count(request_id) == 1
    assert results.count(None) == 1

    with SessionLocal() as db:
        saved = db.get(AgentRequest, request_id)
        assert saved.status in ("completed", "failed")
