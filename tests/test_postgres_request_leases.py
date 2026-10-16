
"""Real PostgreSQL tests for AegisTwin request leases."""

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
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
    renew_request_lease,
)


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_POSTGRES_INTEGRATION") != "1",
    reason="Real PostgreSQL tests disabled.",
)


@pytest.fixture
def records():
    """Create and clean up isolated test records."""

    if (
        os.getenv("DB_NAME") != "aegistwin_test_db"
        or DATABASE_URL.database != "aegistwin_test_db"
        or DATABASE_URL.host not in ("127.0.0.1", "localhost")
        or DATABASE_URL.port not in (55432, 55433)
    ):
        raise RuntimeError("Unsafe database connection.")

    with SessionLocal() as db:
        tenants = [
            Tenant(name=f"Lease-A-{uuid4().hex}"),
            Tenant(name=f"Lease-B-{uuid4().hex}"),
        ]
        db.add_all(tenants)
        db.flush()

        agents = [
            Agent(tenant_id=t.id, name="Lease Agent")
            for t in tenants
        ]
        db.add_all(agents)
        db.flush()

        sessions = [
            AgentSession(tenant_id=t.id, agent_id=a.id)
            for t, a in zip(tenants, agents)
        ]
        db.add_all(sessions)
        db.flush()

        data = {
            "tenants": [t.id for t in tenants],
            "agents": [a.id for a in agents],
            "sessions": [s.id for s in sessions],
        }
        db.commit()

    try:
        yield data
    finally:
        with SessionLocal() as db:
            db.execute(
                delete(AgentRequest).where(
                    AgentRequest.tenant_id.in_(data["tenants"])
                )
            )
            db.execute(
                delete(AgentSession).where(
                    AgentSession.id.in_(data["sessions"])
                )
            )
            db.execute(
                delete(Agent).where(
                    Agent.id.in_(data["agents"])
                )
            )
            db.execute(
                delete(Tenant).where(
                    Tenant.id.in_(data["tenants"])
                )
            )
            db.commit()


def new_request(records, index=0):
    return create_request(
        tenant_id=records["tenants"][index],
        agent_id=records["agents"][index],
        session_id=records["sessions"][index],
        provider="test",
        model="test-model",
        public_request_id=f"REQ-{uuid4().hex[:12]}",
    )


def expire_lease(request_id):
    """Simulate expiry only on the isolated test database."""
    with SessionLocal() as db:
        request = db.get(AgentRequest, request_id)
        request.lease_expires_at = (
            datetime.now(timezone.utc) - timedelta(minutes=5)
        )
        db.commit()


def test_first_worker_acquires_lease(records):
    request_id = new_request(records)
    tenant_id = records["tenants"][0]

    token = acquire_request_lease(
        tenant_id, request_id, "worker-a"
    )

    assert isinstance(token, str)
    assert token

    with SessionLocal() as db:
        saved = db.get(AgentRequest, request_id)
        assert saved.lease_owner_id == "worker-a"
        assert saved.lease_token == token
        assert saved.lease_expires_at is not None
        assert saved.last_heartbeat_at is not None


def test_second_worker_cannot_acquire(records):
    request_id = new_request(records)
    tenant_id = records["tenants"][0]

    first = acquire_request_lease(
        tenant_id, request_id, "worker-a"
    )
    second = acquire_request_lease(
        tenant_id, request_id, "worker-b"
    )

    assert first is not None
    assert second is None


def test_wrong_tenant_cannot_acquire(records):
    request_id = new_request(records)

    result = acquire_request_lease(
        records["tenants"][1],
        request_id,
        "worker-b",
    )

    assert result is None


def test_correct_worker_renews_lease(records):
    request_id = new_request(records)
    tenant_id = records["tenants"][0]

    token = acquire_request_lease(
        tenant_id, request_id, "worker-a"
    )

    assert renew_request_lease(
        tenant_id, request_id, "worker-a", token
    ) is True


def test_wrong_worker_or_token_cannot_renew(records):
    request_id = new_request(records)
    tenant_id = records["tenants"][0]

    token = acquire_request_lease(
        tenant_id, request_id, "worker-a"
    )

    assert renew_request_lease(
        tenant_id, request_id, "worker-b", token
    ) is False

    assert renew_request_lease(
        tenant_id, request_id, "worker-a", "wrong-token"
    ) is False


def test_expired_lease_cannot_renew(records):
    request_id = new_request(records)
    tenant_id = records["tenants"][0]

    token = acquire_request_lease(
        tenant_id, request_id, "worker-a"
    )

    expire_lease(request_id)

    assert renew_request_lease(
        tenant_id, request_id, "worker-a", token
    ) is False


def test_leased_request_requires_token(records):
    request_id = new_request(records)
    tenant_id = records["tenants"][0]

    token = acquire_request_lease(
        tenant_id, request_id, "worker-a"
    )

    assert complete_request(
        request_id, tenant_id, "completed"
    ) is None

    assert complete_request(
        request_id,
        tenant_id,
        "completed",
        lease_token=token,
    ) == request_id


def test_expired_lease_cannot_finalize(records):
    request_id = new_request(records)
    tenant_id = records["tenants"][0]

    token = acquire_request_lease(
        tenant_id, request_id, "worker-a"
    )

    expire_lease(request_id)

    assert complete_request(
        request_id,
        tenant_id,
        "completed",
        lease_token=token,
    ) is None


def test_expired_request_is_recovered(records):
    request_id = new_request(records)
    tenant_id = records["tenants"][0]

    token = acquire_request_lease(
        tenant_id, request_id, "worker-a"
    )

    expire_lease(request_id)

    recovered = recover_expired_requests(tenant_id)

    assert request_id in recovered

    with SessionLocal() as db:
        saved = db.get(AgentRequest, request_id)
        assert saved.status == "recovered"
        assert saved.error_code == "lease_expired"
        assert saved.completed_at is not None

    assert complete_request(
        request_id,
        tenant_id,
        "completed",
        lease_token=token,
    ) is None


def test_active_lease_is_not_recovered(records):
    request_id = new_request(records)
    tenant_id = records["tenants"][0]

    acquire_request_lease(
        tenant_id, request_id, "worker-a"
    )

    assert request_id not in recover_expired_requests(
        tenant_id
    )

    with SessionLocal() as db:
        assert db.get(AgentRequest, request_id).status == "pending"


def test_recovery_is_tenant_scoped(records):
    request_id = new_request(records, index=0)
    tenant_a, tenant_b = records["tenants"]

    acquire_request_lease(
        tenant_a, request_id, "worker-a"
    )
    expire_lease(request_id)

    assert request_id not in recover_expired_requests(
        tenant_b
    )
    assert request_id in recover_expired_requests(
        tenant_a
    )


def test_concurrent_acquisition_has_one_winner(records):
    request_id = new_request(records)
    tenant_id = records["tenants"][0]

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(
                acquire_request_lease,
                tenant_id,
                request_id,
                worker,
            )
            for worker in ("worker-a", "worker-b")
        ]
        results = [f.result() for f in futures]

    assert sum(token is not None for token in results) == 1

# ==========================================================
# CONCURRENCY: COMPLETION VS EXPIRY RECOVERY
# ==========================================================


def test_expired_request_completion_recovery_race(records):
    """An expired worker cannot overwrite recovery."""

    from threading import Barrier

    request_id = new_request(records)
    tenant_id = records["tenants"][0]

    token = acquire_request_lease(
        tenant_id, request_id, "worker-a"
    )
    assert token is not None

    expire_lease(request_id)

    barrier = Barrier(2)

    def finalize():
        barrier.wait(timeout=10)
        return complete_request(
            request_id,
            tenant_id,
            "completed",
            lease_token=token,
        )

    def recover():
        barrier.wait(timeout=10)
        return recover_expired_requests(tenant_id)

    with ThreadPoolExecutor(max_workers=2) as executor:
        completion_future = executor.submit(finalize)
        recovery_future = executor.submit(recover)

        completion_result = completion_future.result(timeout=15)
        recovered_ids = recovery_future.result(timeout=15)

    assert completion_result is None
    assert request_id in recovered_ids

    with SessionLocal() as db:
        saved = db.get(AgentRequest, request_id)
        assert saved.status == "recovered"
        assert saved.error_code == "lease_expired"
        assert saved.completed_at is not None


def test_active_completion_cannot_be_recovered(records):
    """A valid completion must remain terminal."""

    from threading import Barrier

    request_id = new_request(records)
    tenant_id = records["tenants"][0]

    token = acquire_request_lease(
        tenant_id, request_id, "worker-a"
    )
    assert token is not None

    barrier = Barrier(2)

    def finalize():
        barrier.wait(timeout=10)
        return complete_request(
            request_id,
            tenant_id,
            "completed",
            lease_token=token,
        )

    def recover():
        barrier.wait(timeout=10)
        return recover_expired_requests(tenant_id)

    with ThreadPoolExecutor(max_workers=2) as executor:
        completion_future = executor.submit(finalize)
        recovery_future = executor.submit(recover)

        completion_result = completion_future.result(timeout=15)
        recovered_ids = recovery_future.result(timeout=15)

    assert completion_result == request_id
    assert request_id not in recovered_ids

    with SessionLocal() as db:
        saved = db.get(AgentRequest, request_id)
        assert saved.status == "completed"
        assert saved.error_code is None


def test_concurrent_recovery_workers_do_not_duplicate(records):
    """Only one recovery worker may recover an expired row."""

    from threading import Barrier

    request_id = new_request(records)
    tenant_id = records["tenants"][0]

    token = acquire_request_lease(
        tenant_id, request_id, "worker-a"
    )
    assert token is not None

    expire_lease(request_id)

    barrier = Barrier(2)

    def recover():
        barrier.wait(timeout=10)
        return recover_expired_requests(tenant_id)

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(recover)
            for _ in range(2)
        ]
        results = [future.result(timeout=15) for future in futures]

    assert sum(
        request_id in recovered_ids
        for recovered_ids in results
    ) == 1

    with SessionLocal() as db:
        saved = db.get(AgentRequest, request_id)
        assert saved.status == "recovered"
        assert saved.error_code == "lease_expired"
