
"""PostgreSQL concurrency and crash-recovery integration tests.

These tests require the isolated aegistwin_test_db database.

No provider or LLM inference calls are made.
"""

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier
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
    acquire_request_lease,
    complete_request,
    create_request,
    recover_expired_requests,
)


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_POSTGRES_INTEGRATION") != "1",
    reason="PostgreSQL integration tests disabled.",
)


def assert_safe_test_database():
    """Prevent tests from modifying a non-test database."""

    if (
        os.getenv("DB_NAME") != "aegistwin_test_db"
        or DATABASE_URL.database != "aegistwin_test_db"
        or DATABASE_URL.host not in ("localhost", "127.0.0.1")
        or DATABASE_URL.port not in (55432, 55433)
    ):
        raise RuntimeError(
            "Unsafe database connection: refusing to run."
        )


@pytest.fixture
def records():
    """Create isolated tenant, agent and session records."""

    assert_safe_test_database()

    with SessionLocal() as db:
        tenant = Tenant(
            name=f"Concurrency-Test-{uuid4().hex}"
        )
        db.add(tenant)
        db.flush()

        agent = Agent(
            tenant_id=tenant.id,
            name="Concurrency Test Agent",
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


def create_test_request(records, *, expired=False):
    """Create a real leased PostgreSQL request."""

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
        worker_id=f"concurrency-worker-{uuid4().hex}",
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

    return request_id, token


# ==========================================================
# TWO WORKERS RECOVERING THE SAME REQUEST
# ==========================================================


def test_concurrent_recovery_does_not_duplicate_transition(records):
    """Two simultaneous recovery calls may recover a row only once."""

    request_id, _ = create_test_request(
        records,
        expired=True,
    )

    barrier = Barrier(2)

    def recover():
        barrier.wait(timeout=10)

        return recover_expired_requests(
            tenant_id=records["tenant_id"],
            limit=10,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(recover)
            for _ in range(2)
        ]

        results = [
            future.result(timeout=20)
            for future in futures
        ]

    recovered_ids = [
        recovered_id
        for result in results
        for recovered_id in result
    ]

    assert recovered_ids.count(request_id) == 1

    with SessionLocal() as db:
        row = db.get(AgentRequest, request_id)

        assert row.status == "recovered"
        assert row.error_code == "lease_expired"
        assert row.completed_at is not None


# ==========================================================
# STALE WORKER CANNOT FINALIZE AFTER RECOVERY
# ==========================================================


def test_stale_worker_cannot_finalize_recovered_request(records):
    """A late provider result cannot overwrite recovery."""

    request_id, lease_token = create_test_request(
        records,
        expired=True,
    )

    recovered_ids = recover_expired_requests(
        tenant_id=records["tenant_id"],
        limit=10,
    )

    assert request_id in recovered_ids

    finalized = complete_request(
        request_id=request_id,
        tenant_id=records["tenant_id"],
        status="completed",
        lease_token=lease_token,
    )

    assert finalized is None

    with SessionLocal() as db:
        row = db.get(AgentRequest, request_id)

        assert row.status == "recovered"
        assert row.error_code == "lease_expired"


# ==========================================================
# FINISHED REQUEST CANNOT BE RECOVERED
# ==========================================================


def test_completed_request_cannot_be_recovered(records):
    """A committed completion remains terminal."""

    request_id, lease_token = create_test_request(
        records,
        expired=False,
    )

    finalized = complete_request(
        request_id=request_id,
        tenant_id=records["tenant_id"],
        status="completed",
        lease_token=lease_token,
    )

    assert finalized == request_id

    # Simulate time passing beyond the original lease.
    with SessionLocal() as db:
        row = db.get(AgentRequest, request_id)

        row.lease_expires_at = (
            datetime.now(timezone.utc)
            - timedelta(minutes=5)
        )

        db.commit()

    recovered_ids = recover_expired_requests(
        tenant_id=records["tenant_id"],
        limit=10,
    )

    assert request_id not in recovered_ids

    with SessionLocal() as db:
        row = db.get(AgentRequest, request_id)

        assert row.status == "completed"
        assert row.error_code != "lease_expired"

def test_concurrent_finalization_and_recovery(records):
    """Recovery and finalization must not both succeed."""

    request_id, lease_token = create_test_request(
        records,
        expired=True,
    )

    barrier = Barrier(2)

    def finalize():
        barrier.wait(timeout=10)

        return complete_request(
            request_id=request_id,
            tenant_id=records["tenant_id"],
            status="completed",
            lease_token=lease_token,
        )

    def recover():
        barrier.wait(timeout=10)

        return recover_expired_requests(
            tenant_id=records["tenant_id"],
            limit=10,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        finalize_future = executor.submit(finalize)
        recover_future = executor.submit(recover)

        finalized = finalize_future.result(timeout=20)
        recovered_ids = recover_future.result(timeout=20)

    with SessionLocal() as db:
        row = db.get(AgentRequest, request_id)

        # An expired lease cannot finalize the request.
        assert finalized is None

        # Recovery must win for an already expired lease.
        assert request_id in recovered_ids

        assert row.status == "recovered"
        assert row.error_code == "lease_expired"
