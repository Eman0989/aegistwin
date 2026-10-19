
"""Real PostgreSQL integration tests for the recovery worker."""

import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import delete, select

from app.infrastructure.database import DATABASE_URL, SessionLocal
from app.infrastructure.models import (
    Agent,
    AgentRequest,
    AgentSession,
    Tenant,
)
from app.infrastructure.persistence import acquire_request_lease
from app.infrastructure.recovery_worker import (
    RecoveryWorker,
    discover_expired_tenants,
    run_recovery_cycle,
)


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_POSTGRES_INTEGRATION") != "1",
    reason="PostgreSQL integration tests disabled.",
)


@pytest.fixture
def records():
    """Create and clean up isolated test records."""

    if (
        os.getenv("DB_NAME") != "aegistwin_test_db"
        or DATABASE_URL.database != "aegistwin_test_db"
        or DATABASE_URL.host not in ("localhost", "127.0.0.1")
        or DATABASE_URL.port not in (55432, 55433)
    ):
        raise RuntimeError("Unsafe database connection.")

    with SessionLocal() as db:
        tenant = Tenant(name=f"Recovery-Worker-{uuid4().hex}")
        db.add(tenant)
        db.flush()

        agent = Agent(
            tenant_id=tenant.id,
            name="Recovery Test Agent",
        )
        db.add(agent)
        db.flush()

        session = AgentSession(
            tenant_id=tenant.id,
            agent_id=agent.id,
        )
        db.add(session)
        db.flush()

        data = {
            "tenant_id": tenant.id,
            "agent_id": agent.id,
            "session_id": session.id,
        }
        db.commit()

    try:
        yield data
    finally:
        with SessionLocal() as db:
            db.execute(
                delete(AgentRequest).where(
                    AgentRequest.tenant_id == data["tenant_id"]
                )
            )
            db.execute(
                delete(AgentSession).where(
                    AgentSession.id == data["session_id"]
                )
            )
            db.execute(
                delete(Agent).where(
                    Agent.id == data["agent_id"]
                )
            )
            db.execute(
                delete(Tenant).where(
                    Tenant.id == data["tenant_id"]
                )
            )
            db.commit()


def create_leased_request(records, *, expired=False):
    """Create a test request and acquire a real lease."""

    from app.infrastructure.persistence import create_request

    request_id = create_request(
        tenant_id=records["tenant_id"],
        agent_id=records["agent_id"],
        session_id=records["session_id"],
        provider="test",
        model="test-model",
        public_request_id=f"REQ-{uuid4().hex}",
    )

    token = acquire_request_lease(
        tenant_id=records["tenant_id"],
        request_id=request_id,
        worker_id=f"test-worker-{uuid4().hex}",
        lease_seconds=60,
    )

    assert token is not None

    if expired:
        with SessionLocal() as db:
            row = db.get(AgentRequest, request_id)
            row.lease_expires_at = (
                datetime.now(timezone.utc)
                - timedelta(minutes=5)
            )
            db.commit()

    return request_id


def test_discovers_expired_tenant(records):
    request_id = create_leased_request(records, expired=True)

    tenants = discover_expired_tenants(limit=100)

    assert records["tenant_id"] in tenants

    with SessionLocal() as db:
        assert db.get(AgentRequest, request_id).status == "pending"


def test_cycle_recovers_expired_request(records):
    request_id = create_leased_request(records, expired=True)

    stats = run_recovery_cycle()

    assert stats.requests_recovered >= 1

    with SessionLocal() as db:
        row = db.get(AgentRequest, request_id)
        assert row.status == "recovered"
        assert row.error_code == "lease_expired"
        assert row.completed_at is not None


def test_active_lease_remains_pending(records):
    request_id = create_leased_request(records, expired=False)

    run_recovery_cycle()

    with SessionLocal() as db:
        row = db.get(AgentRequest, request_id)
        assert row.status == "pending"


def test_completed_request_is_not_recovered(records):
    from app.infrastructure.persistence import complete_request

    request_id = create_leased_request(records)

    with SessionLocal() as db:
        row = db.get(AgentRequest, request_id)
        token = row.lease_token

    completed = complete_request(
        request_id=request_id,
        tenant_id=records["tenant_id"],
        status="completed",
        lease_token=token,
    )

    assert completed == request_id

    run_recovery_cycle()

    with SessionLocal() as db:
        row = db.get(AgentRequest, request_id)
        assert row.status == "completed"


def test_recovery_is_idempotent(records):
    request_id = create_leased_request(records, expired=True)

    first = run_recovery_cycle()
    second = run_recovery_cycle()

    assert first.requests_recovered >= 1
    assert second.requests_recovered == 0

    with SessionLocal() as db:
        assert db.get(AgentRequest, request_id).status == "recovered"


def test_worker_run_once_uses_real_database(records):
    request_id = create_leased_request(records, expired=True)

    worker = RecoveryWorker(
        batch_size=10,
        tenant_limit=100,
    )

    stats = worker.run_once()

    assert stats.requests_recovered >= 1

    with SessionLocal() as db:
        assert db.get(AgentRequest, request_id).status == "recovered"

def test_worker_rotates_between_real_postgres_tenants(records):
    """Verify tenant rotation using three real PostgreSQL tenants.

    Limit discovery to test-owned tenant IDs so unrelated
    expired requests cannot interfere with the assertions.
    """

    from unittest.mock import patch

    from sqlalchemy import func

    import app.infrastructure.recovery_worker as recovery_module

    first_request = create_leased_request(
        records,
        expired=True,
    )

    tenant_records = [records]
    additional_records = []
    request_ids = [first_request]

    try:
        # Create two additional test tenants.
        with SessionLocal() as db:
            for _ in range(2):
                tenant = Tenant(
                    name=f"Fairness-Test-{uuid4().hex}"
                )
                db.add(tenant)
                db.flush()

                agent = Agent(
                    tenant_id=tenant.id,
                    name="Fairness Test Agent",
                )
                db.add(agent)
                db.flush()

                session = AgentSession(
                    tenant_id=tenant.id,
                    agent_id=agent.id,
                )
                db.add(session)
                db.flush()

                item = {
                    "tenant_id": tenant.id,
                    "agent_id": agent.id,
                    "session_id": session.id,
                }

                additional_records.append(item)
                tenant_records.append(item)

            db.commit()

        for item in additional_records:
            request_ids.append(
                create_leased_request(
                    item,
                    expired=True,
                )
            )

        allowed_tenant_ids = {
            item["tenant_id"] for item in tenant_records
        }

        real_session_local = recovery_module.SessionLocal

        class IsolatedSession:
            """Scope discovery SQL to the test-owned tenants."""

            def __enter__(self):
                self.db = real_session_local()
                return self

            def __exit__(self, exc_type, exc, tb):
                self.db.close()

            def execute(self, statement):
                # This test invokes SessionLocal only for
                # tenant discovery. Add tenant isolation to
                # the real SQL query before executing it.
                statement = statement.where(
                    AgentRequest.tenant_id.in_(
                        allowed_tenant_ids
                    )
                )
                return self.db.execute(statement)

        worker = RecoveryWorker(
            batch_size=1,
            tenant_limit=1,
        )

        visited_tenants = []

        with patch.object(
            recovery_module,
            "SessionLocal",
            side_effect=IsolatedSession,
        ):
            for _ in range(3):
                stats = worker.run_once()

                assert stats.tenants_scanned == 1
                assert stats.requests_recovered == 1

                visited_tenants.append(
                    worker.last_tenant_id
                )

        # All three tenants should receive recovery service.
        assert set(visited_tenants) == allowed_tenant_ids
        assert len(set(visited_tenants)) == 3

        with SessionLocal() as db:
            for request_id in request_ids:
                row = db.get(AgentRequest, request_id)
                assert row.status == "recovered"
                assert row.error_code == "lease_expired"

    finally:
        # The existing records fixture cleans up the first tenant.
        # Clean up only the two tenants created here.
        with SessionLocal() as db:
            for item in additional_records:
                db.execute(
                    delete(AgentRequest).where(
                        AgentRequest.tenant_id
                        == item["tenant_id"]
                    )
                )
                db.execute(
                    delete(AgentSession).where(
                        AgentSession.id
                        == item["session_id"]
                    )
                )
                db.execute(
                    delete(Agent).where(
                        Agent.id
                        == item["agent_id"]
                    )
                )
                db.execute(
                    delete(Tenant).where(
                        Tenant.id
                        == item["tenant_id"]
                    )
                )

            db.commit()
