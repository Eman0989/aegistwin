
"""PostgreSQL integration tests for request reliability.

These tests require an isolated PostgreSQL 18 database.

Required configuration:
    DB_NAME=aegistwin_test_db
    DB_HOST=127.0.0.1
    DB_PORT=55432
    RUN_POSTGRES_INTEGRATION=1

The database must have the latest Alembic migrations applied.

Tests are skipped by default and clean up only their own records.
"""

import os
import threading
import uuid

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.exc import IntegrityError


# Prevent accidental execution against a real database.
pytestmark = pytest.mark.skipif(
    os.getenv("RUN_POSTGRES_INTEGRATION") != "1",
    reason=(
        "Explicitly enable isolated PostgreSQL tests "
        "with RUN_POSTGRES_INTEGRATION=1"
    ),
)


def _guard_database():
    """Reject unsafe database configurations."""

    if os.getenv("RUN_POSTGRES_INTEGRATION") != "1":
        raise RuntimeError(
            "PostgreSQL integration tests must be explicitly enabled"
        )

    if os.getenv("DB_NAME") != "aegistwin_test_db":
        raise RuntimeError(
            "Refusing to use a database other than aegistwin_test_db"
        )

    if os.getenv("DB_HOST") not in {"localhost", "127.0.0.1"}:
        raise RuntimeError(
            "Tests require a local PostgreSQL host"
        )

    if os.getenv("DB_PORT") != "55432":
        raise RuntimeError(
            "Tests require DB_PORT=55432"
        )

    from app.infrastructure.database import DATABASE_URL

    if (
        DATABASE_URL.drivername != "postgresql+psycopg"
        or DATABASE_URL.database != "aegistwin_test_db"
        or DATABASE_URL.host not in {"localhost", "127.0.0.1"}
        or DATABASE_URL.port != 55432
    ):
        raise RuntimeError(
            "Application database URL is not the safe test URL"
        )


@pytest.fixture
def records():
    """Create isolated test records with scoped cleanup."""

    _guard_database()

    from sqlalchemy import delete

    from app.infrastructure.database import SessionLocal
    from app.infrastructure.models import (
        Tenant,
        Agent,
        AgentSession,
        AgentRequest,
    )
    from app.infrastructure.persistence import (
        create_session,
        create_request,
    )

    ids = {
        "tenants": [],
        "agents": [],
        "sessions": [],
        "requests": [],
    }

    def make_tenant():
        identifier = uuid.uuid4().hex[:12]

        with SessionLocal.begin() as db:
            tenant = Tenant(
                name=f"Request Reliability Test {identifier}"
            )
            db.add(tenant)
            db.flush()

            agent = Agent(
                tenant_id=tenant.id,
                name=f"Reliability Agent {identifier}",
            )
            db.add(agent)
            db.flush()

            tenant_id = tenant.id
            agent_id = agent.id

        ids["tenants"].append(tenant_id)
        ids["agents"].append(agent_id)

        session_id = create_session(
            tenant_id=tenant_id,
            agent_id=agent_id,
        )

        ids["sessions"].append(session_id)

        return {
            "tenant_id": tenant_id,
            "agent_id": agent_id,
            "session_id": session_id,
        }

    def make_request(scope, public_request_id=None):
        request_id = create_request(
            tenant_id=scope["tenant_id"],
            agent_id=scope["agent_id"],
            session_id=scope["session_id"],
            provider="ollama",
            model="llama3",
            public_request_id=public_request_id,
        )

        ids["requests"].append(request_id)

        return request_id

    try:
        yield make_tenant, make_request

    finally:
        # Delete only records created by these tests.
        with SessionLocal.begin() as db:

            if ids["requests"]:
                db.execute(
                    delete(AgentRequest).where(
                        AgentRequest.id.in_(ids["requests"])
                    )
                )

            if ids["sessions"]:
                db.execute(
                    delete(AgentSession).where(
                        AgentSession.id.in_(ids["sessions"])
                    )
                )

            if ids["agents"]:
                db.execute(
                    delete(Agent).where(
                        Agent.id.in_(ids["agents"])
                    )
                )

            if ids["tenants"]:
                db.execute(
                    delete(Tenant).where(
                        Tenant.id.in_(ids["tenants"])
                    )
                )


def _state(request_id):
    """Read the current database state of a request."""

    from app.infrastructure.database import SessionLocal
    from app.infrastructure.models import AgentRequest

    with SessionLocal() as db:
        request = db.get(AgentRequest, request_id)

        assert request is not None

        return {
            "status": request.status,
            "public_request_id": request.public_request_id,
            "lease_token": request.lease_token,
            "lease_owner_id": request.lease_owner_id,
            "lease_expires_at": request.lease_expires_at,
            "last_heartbeat_at": request.last_heartbeat_at,
            "completed_at": request.completed_at,
            "error_code": request.error_code,
        }


def _expire(request_id):
    """Expire the lease of one disposable test request."""

    from sqlalchemy import update
    from app.infrastructure.database import SessionLocal
    from app.infrastructure.models import AgentRequest

    expired_time = (
        datetime.now(timezone.utc) - timedelta(minutes=1)
    )

    with SessionLocal.begin() as db:
        db.execute(
            update(AgentRequest)
            .where(AgentRequest.id == request_id)
            .values(lease_expires_at=expired_time)
        )


# ---------------------------------------------------------
# TEST 1: Public request ID and tenant uniqueness
# ---------------------------------------------------------

def test_public_request_id_and_tenant_scoped_uniqueness(records):

    make_tenant, make_request = records

    first = make_tenant()
    second = make_tenant()

    public_id = f"REQ-{uuid.uuid4().hex[:12].upper()}"

    first_id = make_request(
        first,
        public_request_id=public_id,
    )

    assert _state(first_id)["public_request_id"] == public_id

    # Different tenants may use the same public ID.
    second_id = make_request(
        second,
        public_request_id=public_id,
    )

    assert _state(second_id)["public_request_id"] == public_id

    # Duplicate public ID within the same tenant must fail.
    with pytest.raises(IntegrityError):
        make_request(
            first,
            public_request_id=public_id,
        )

    assert _state(first_id)["status"] == "pending"


# ---------------------------------------------------------
# TEST 2: Legacy request finalization
# ---------------------------------------------------------

def test_unleased_legacy_finalization_is_one_time(records):

    from app.infrastructure.persistence import complete_request

    make_tenant, make_request = records

    scope = make_tenant()
    request_id = make_request(scope)

    result = complete_request(
        request_id,
        scope["tenant_id"],
        "completed",
    )

    assert result == request_id

    # A second finalization must not overwrite the first.
    result_again = complete_request(
        request_id,
        scope["tenant_id"],
        "failed",
    )

    assert result_again is None
    assert _state(request_id)["status"] == "completed"


# ---------------------------------------------------------
# TEST 3: Simultaneous lease acquisition
# ---------------------------------------------------------

def test_simultaneous_claims_have_exactly_one_winner(records):

    from app.infrastructure.persistence import acquire_request_lease

    make_tenant, make_request = records

    scope = make_tenant()
    request_id = make_request(scope)

    barrier = threading.Barrier(6)

    def attempt(index):
        barrier.wait(timeout=15)

        return acquire_request_lease(
            scope["tenant_id"],
            request_id,
            f"worker-{index}",
        )

    with ThreadPoolExecutor(max_workers=6) as executor:
        outcomes = list(
            executor.map(attempt, range(6))
        )

    winning_tokens = [
        token
        for token in outcomes
        if token is not None
    ]

    assert len(winning_tokens) == 1

    assert (
        winning_tokens[0]
        == _state(request_id)["lease_token"]
    )


# ---------------------------------------------------------
# TEST 4: Lease renewal authorization
# ---------------------------------------------------------

def test_lease_renewal_requires_correct_tenant_worker_and_token(
    records,
):

    from app.infrastructure.persistence import (
        acquire_request_lease,
        renew_request_lease,
    )

    make_tenant, make_request = records

    scope = make_tenant()
    other_scope = make_tenant()

    request_id = make_request(scope)

    token = acquire_request_lease(
        scope["tenant_id"],
        request_id,
        "worker-a",
        10,
    )

    assert token

    before = _state(request_id)

    # Wrong tenant.
    assert not renew_request_lease(
        other_scope["tenant_id"],
        request_id,
        "worker-a",
        token,
    )

    # Wrong worker.
    assert not renew_request_lease(
        scope["tenant_id"],
        request_id,
        "worker-b",
        token,
    )

    # Wrong lease token.
    assert not renew_request_lease(
        scope["tenant_id"],
        request_id,
        "worker-a",
        "wrong-token",
    )

    # Valid lease owner.
    assert renew_request_lease(
        scope["tenant_id"],
        request_id,
        "worker-a",
        token,
        120,
    )

    after = _state(request_id)

    assert (
        after["lease_expires_at"]
        > before["lease_expires_at"]
    )

    assert (
        after["last_heartbeat_at"]
        >= before["last_heartbeat_at"]
    )


# ---------------------------------------------------------
# TEST 5: Expired lease renewal
# ---------------------------------------------------------

def test_expired_lease_cannot_be_renewed(records):

    from app.infrastructure.persistence import (
        acquire_request_lease,
        renew_request_lease,
    )

    make_tenant, make_request = records

    scope = make_tenant()
    request_id = make_request(scope)

    token = acquire_request_lease(
        scope["tenant_id"],
        request_id,
        "worker-a",
    )

    _expire(request_id)

    assert not renew_request_lease(
        scope["tenant_id"],
        request_id,
        "worker-a",
        token,
    )


# ---------------------------------------------------------
# TEST 6: Finalization requires a valid lease
# ---------------------------------------------------------

def test_leased_request_cannot_be_finalized_without_valid_lease(
    records,
):

    from app.infrastructure.persistence import (
        acquire_request_lease,
        complete_request,
    )

    make_tenant, make_request = records

    scope = make_tenant()
    other_scope = make_tenant()

    request_id = make_request(scope)

    token = acquire_request_lease(
        scope["tenant_id"],
        request_id,
        "worker-a",
    )

    # Missing lease.
    assert complete_request(
        request_id,
        scope["tenant_id"],
        "completed",
    ) is None

    # Wrong tenant.
    assert complete_request(
        request_id,
        other_scope["tenant_id"],
        "completed",
        worker_id="worker-a",
        lease_token=token,
    ) is None

    # Wrong worker.
    assert complete_request(
        request_id,
        scope["tenant_id"],
        "completed",
        worker_id="worker-b",
        lease_token=token,
    ) is None

    # Wrong token.
    assert complete_request(
        request_id,
        scope["tenant_id"],
        "completed",
        worker_id="worker-a",
        lease_token="wrong",
    ) is None

    # Correct lease owner.
    assert complete_request(
        request_id,
        scope["tenant_id"],
        "completed",
        worker_id="worker-a",
        lease_token=token,
    ) == request_id

    # Duplicate finalization.
    assert complete_request(
        request_id,
        scope["tenant_id"],
        "failed",
        worker_id="worker-a",
        lease_token=token,
    ) is None

    assert _state(request_id)["status"] == "completed"


# ---------------------------------------------------------
# TEST 7: Concurrent duplicate finalization
# ---------------------------------------------------------

def test_concurrent_duplicate_finalization_only_one_commits(
    records,
):

    from app.infrastructure.persistence import (
        acquire_request_lease,
        complete_request,
    )

    make_tenant, make_request = records

    scope = make_tenant()
    request_id = make_request(scope)

    token = acquire_request_lease(
        scope["tenant_id"],
        request_id,
        "worker-a",
    )

    barrier = threading.Barrier(2)

    def finalize(status):
        barrier.wait(timeout=15)

        return complete_request(
            request_id,
            scope["tenant_id"],
            status,
            worker_id="worker-a",
            lease_token=token,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(
            executor.map(
                finalize,
                ("completed", "failed"),
            )
        )

    assert outcomes.count(request_id) == 1
    assert outcomes.count(None) == 1

    assert _state(request_id)["status"] in {
        "completed",
        "failed",
    }


# ---------------------------------------------------------
# TEST 8: Tenant-scoped recovery
# ---------------------------------------------------------

def test_recovery_is_tenant_scoped_and_terminal(records):

    from app.infrastructure.persistence import (
        acquire_request_lease,
        complete_request,
        recover_expired_requests,
        renew_request_lease,
    )

    make_tenant, make_request = records

    tenant_a = make_tenant()
    tenant_b = make_tenant()

    req_a = make_request(tenant_a)
    req_b = make_request(tenant_b)

    token_a = acquire_request_lease(
        tenant_a["tenant_id"],
        req_a,
        "worker-a",
    )

    acquire_request_lease(
        tenant_b["tenant_id"],
        req_b,
        "worker-b",
    )

    _expire(req_a)
    _expire(req_b)

    # Recover only tenant A.
    assert recover_expired_requests(
        tenant_a["tenant_id"]
    ) == 1

    assert _state(req_a)["status"] == "recovered"
    assert _state(req_a)["error_code"] == "LEASE_EXPIRED"

    # Tenant B must remain unchanged.
    assert _state(req_b)["status"] == "pending"

    # Late worker cannot finalize recovered record.
    assert complete_request(
        req_a,
        tenant_a["tenant_id"],
        "completed",
        worker_id="worker-a",
        lease_token=token_a,
    ) is None

    # Recovered leases cannot be renewed.
    assert not renew_request_lease(
        tenant_a["tenant_id"],
        req_a,
        "worker-a",
        token_a,
    )

    # Recovery is terminal and not repeatable.
    assert recover_expired_requests(
        tenant_a["tenant_id"]
    ) == 0

    assert recover_expired_requests(
        tenant_b["tenant_id"]
    ) == 1


# ---------------------------------------------------------
# TEST 9: Recovery limit and unleased requests
# ---------------------------------------------------------

def test_recovery_respects_limit_and_ignores_unleased_requests(
    records,
):

    from app.infrastructure.persistence import (
        acquire_request_lease,
        recover_expired_requests,
    )

    make_tenant, make_request = records

    scope = make_tenant()

    first, second, unleased = (
        make_request(scope)
        for _ in range(3)
    )

    acquire_request_lease(
        scope["tenant_id"],
        first,
        "worker-a",
    )

    acquire_request_lease(
        scope["tenant_id"],
        second,
        "worker-b",
    )

    _expire(first)
    _expire(second)

    assert recover_expired_requests(
        scope["tenant_id"],
        limit=1,
    ) == 1

    recovered_count = sum(
        _state(request_id)["status"] == "recovered"
        for request_id in (first, second)
    )

    assert recovered_count == 1

    assert recover_expired_requests(
        scope["tenant_id"],
        limit=1,
    ) == 1

    assert _state(unleased)["status"] == "pending"


# ---------------------------------------------------------
# TEST 10: Completion versus recovery (valid lease)
# ---------------------------------------------------------

def test_completion_and_recovery_concurrently_preserve_completed(
    records,
):

    from app.infrastructure.persistence import (
        acquire_request_lease,
        complete_request,
        recover_expired_requests,
    )

    make_tenant, make_request = records

    scope = make_tenant()
    request_id = make_request(scope)

    token = acquire_request_lease(
        scope["tenant_id"],
        request_id,
        "worker-a",
        60,
    )

    barrier = threading.Barrier(2)

    def completion():
        barrier.wait(timeout=15)

        return complete_request(
            request_id,
            scope["tenant_id"],
            "completed",
            worker_id="worker-a",
            lease_token=token,
        )

    def recovery():
        barrier.wait(timeout=15)

        return recover_expired_requests(
            scope["tenant_id"]
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        future_a = executor.submit(completion)
        future_b = executor.submit(recovery)

        assert future_a.result(timeout=20) == request_id
        assert future_b.result(timeout=20) == 0

    assert _state(request_id)["status"] == "completed"

    assert recover_expired_requests(
        scope["tenant_id"]
    ) == 0


# ---------------------------------------------------------
# TEST 11: Completion versus recovery (expired lease)
# ---------------------------------------------------------

def test_completion_and_recovery_concurrently_preserve_recovered(
    records,
):

    from app.infrastructure.persistence import (
        acquire_request_lease,
        complete_request,
        recover_expired_requests,
    )

    make_tenant, make_request = records

    scope = make_tenant()
    request_id = make_request(scope)

    token = acquire_request_lease(
        scope["tenant_id"],
        request_id,
        "worker-a",
    )

    _expire(request_id)

    barrier = threading.Barrier(2)

    def late_completion():
        barrier.wait(timeout=15)

        return complete_request(
            request_id,
            scope["tenant_id"],
            "completed",
            worker_id="worker-a",
            lease_token=token,
        )

    def recovery():
        barrier.wait(timeout=15)

        return recover_expired_requests(
            scope["tenant_id"]
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        future_a = executor.submit(late_completion)
        future_b = executor.submit(recovery)

        assert future_a.result(timeout=20) is None
        assert future_b.result(timeout=20) == 1

    assert _state(request_id)["status"] == "recovered"
    assert _state(request_id)["completed_at"] is not None
