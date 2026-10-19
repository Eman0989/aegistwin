
"""PostgreSQL integration tests for atomic request creation and leasing."""

import os
from uuid import uuid4

import pytest
from sqlalchemy import delete, select

from app.contracts import TrustedIdentityContext
from app.gateway.postgres_request_lifecycle import (
    finish_request,
    start_leased_request,
)
from app.gateway.postgres_session_resolver import SessionAccessDenied
from app.infrastructure.database import (
    DATABASE_URL,
    SessionLocal,
)
from app.infrastructure.models import (
    Agent,
    AgentRequest,
    AgentSession,
    Tenant,
)


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_POSTGRES_INTEGRATION") != "1",
    reason="PostgreSQL integration tests disabled.",
)


# ==========================================================
# DATABASE SAFETY
# ==========================================================


def verify_test_database():
    """Never run destructive integration tests on production data."""

    if (
        os.getenv("DB_NAME") != "aegistwin_test_db"
        or DATABASE_URL.database != "aegistwin_test_db"
        or DATABASE_URL.host not in ("localhost", "127.0.0.1")
        or DATABASE_URL.port not in (55432, 55433)
    ):
        raise RuntimeError(
            "Refusing to execute against a non-test database."
        )


def make_identity(tenant_id, agent_id, session_id):
    return TrustedIdentityContext(
        tenant_id=str(tenant_id),
        agent_id=str(agent_id),
        session_id=str(session_id),
        user_id="atomic-lease-test",
    )


# ==========================================================
# ISOLATED DATABASE FIXTURE
# ==========================================================


@pytest.fixture
def records():
    verify_test_database()

    with SessionLocal() as db:
        tenants = [
            Tenant(name=f"Atomic-Tenant-A-{uuid4().hex}"),
            Tenant(name=f"Atomic-Tenant-B-{uuid4().hex}"),
        ]

        db.add_all(tenants)
        db.flush()

        agents = [
            Agent(
                tenant_id=tenant.id,
                name="Atomic Test Agent",
            )
            for tenant in tenants
        ]

        db.add_all(agents)
        db.flush()

        sessions = [
            AgentSession(
                tenant_id=tenant.id,
                agent_id=agent.id,
            )
            for tenant, agent in zip(tenants, agents)
        ]

        db.add_all(sessions)
        db.flush()

        data = {
            "tenants": [tenant.id for tenant in tenants],
            "agents": [agent.id for agent in agents],
            "sessions": [session.id for session in sessions],
        }

        db.commit()

    try:
        yield data

    finally:
        with SessionLocal() as db:
            db.execute(
                delete(AgentRequest).where(
                    AgentRequest.tenant_id.in_(
                        data["tenants"]
                    )
                )
            )

            db.execute(
                delete(AgentSession).where(
                    AgentSession.id.in_(
                        data["sessions"]
                    )
                )
            )

            db.execute(
                delete(Agent).where(
                    Agent.id.in_(
                        data["agents"]
                    )
                )
            )

            db.execute(
                delete(Tenant).where(
                    Tenant.id.in_(
                        data["tenants"]
                    )
                )
            )

            db.commit()


def create_atomic_request(
    db,
    records,
    worker_id="worker-atomic-test",
):
    return start_leased_request(
        identity=make_identity(
            records["tenants"][0],
            records["agents"][0],
            records["sessions"][0],
        ),
        public_request_id=f"REQ-{uuid4().hex}",
        provider="ollama",
        model="llama3.2:3b",
        worker_id=worker_id,
        lease_seconds=60,
        db=db,
    )


# ==========================================================
# TEST 1 — REQUEST AND LEASE COMMIT TOGETHER
# ==========================================================


def test_request_and_lease_commit_together(records):
    with SessionLocal() as db:
        request = create_atomic_request(
            db,
            records,
        )

        assert request.lease_token is not None

        # Both objects should be represented by one row
        # in the current uncommitted transaction.
        pending = db.get(
            AgentRequest,
            request.request_id,
        )

        assert pending is not None
        assert pending.status == "pending"
        assert pending.lease_owner_id == "worker-atomic-test"
        assert pending.lease_token == request.lease_token
        assert pending.lease_expires_at is not None
        assert pending.last_heartbeat_at is not None

        db.commit()

    # Verify from a separate database session.
    with SessionLocal() as db:
        saved = db.get(
            AgentRequest,
            request.request_id,
        )

        assert saved is not None
        assert saved.status == "pending"
        assert saved.lease_token == request.lease_token
        assert saved.lease_owner_id == "worker-atomic-test"
        assert saved.lease_expires_at is not None
        assert saved.last_heartbeat_at is not None


# ==========================================================
# TEST 2 — ROLLBACK REMOVES REQUEST AND LEASE
# ==========================================================


def test_rollback_removes_request_and_lease(records):
    with SessionLocal() as db:
        request = create_atomic_request(
            db,
            records,
        )

        request_id = request.request_id

        assert request.lease_token is not None

        # Simulate failure before commit.
        db.rollback()

    with SessionLocal() as db:
        saved = db.get(
            AgentRequest,
            request_id,
        )

        # The entire request row must be absent.
        assert saved is None


# ==========================================================
# TEST 3 — INVALID WORKER REJECTED BEFORE INSERTION
# ==========================================================


@pytest.mark.parametrize(
    "worker_id",
    [
        "",
        " ",
        None,
        123,
        "x" * 151,
    ],
)
def test_invalid_worker_prevents_request_creation(
    records,
    worker_id,
):
    public_id = f"REQ-{uuid4().hex}"

    with SessionLocal() as db:
        with pytest.raises(ValueError):
            start_leased_request(
                identity=make_identity(
                    records["tenants"][0],
                    records["agents"][0],
                    records["sessions"][0],
                ),
                public_request_id=public_id,
                provider="ollama",
                model="llama3.2:3b",
                worker_id=worker_id,
                db=db,
            )

        db.rollback()

    with SessionLocal() as db:
        saved = db.execute(
            select(AgentRequest).where(
                AgentRequest.tenant_id
                == records["tenants"][0],
                AgentRequest.public_request_id
                == public_id,
            )
        ).scalar_one_or_none()

        assert saved is None


# ==========================================================
# TEST 4 — TENANT AND SESSION AUTHORIZATION
# ==========================================================


def test_cross_tenant_session_is_rejected(records):
    public_id = f"REQ-{uuid4().hex}"

    # Tenant B cannot use Tenant A's session.
    unauthorized_identity = make_identity(
        records["tenants"][1],
        records["agents"][1],
        records["sessions"][0],
    )

    with SessionLocal() as db:
        with pytest.raises(SessionAccessDenied):
            start_leased_request(
                identity=unauthorized_identity,
                public_request_id=public_id,
                provider="ollama",
                model="llama3.2:3b",
                worker_id="worker-unauthorized",
                db=db,
            )

        db.rollback()

    with SessionLocal() as db:
        saved = db.execute(
            select(AgentRequest).where(
                AgentRequest.public_request_id
                == public_id,
            )
        ).scalar_one_or_none()

        assert saved is None


# ==========================================================
# TEST 5 — LEASE TOKEN REQUIRED FOR FINALIZATION
# ==========================================================


def test_atomic_request_requires_lease_for_finalization(
    records,
):
    with SessionLocal() as db:
        request = create_atomic_request(
            db,
            records,
        )
        db.commit()

    from app.infrastructure.persistence import complete_request

    # Finalization without ownership must be rejected.
    rejected = complete_request(
        request_id=request.request_id,
        tenant_id=request.tenant_id,
        status="completed",
    )

    assert rejected is None

    # The valid lease holder can finalize.
    finalized = finish_request(
        request=request,
        outcome="completed",
        latency_ms=12.0,
        input_tokens=5,
        output_tokens=10,
    )

    assert finalized == request.request_id

    with SessionLocal() as db:
        saved = db.get(
            AgentRequest,
            request.request_id,
        )

        assert saved.status == "completed"
        assert saved.input_tokens == 5
        assert saved.output_tokens == 10


# ==========================================================
# TEST 6 — DUPLICATE PUBLIC REQUEST ID IS REJECTED
# ==========================================================


def test_duplicate_public_request_id_is_rejected(records):
    from sqlalchemy.exc import IntegrityError

    public_id = f"REQ-{uuid4().hex}"

    with SessionLocal() as db:
        first = start_leased_request(
            identity=make_identity(
                records["tenants"][0],
                records["agents"][0],
                records["sessions"][0],
            ),
            public_request_id=public_id,
            provider="ollama",
            model="llama3.2:3b",
            worker_id="worker-first",
            db=db,
        )

        db.commit()

    assert first.lease_token is not None

    with SessionLocal() as db:
        with pytest.raises(IntegrityError):
            start_leased_request(
                identity=make_identity(
                    records["tenants"][0],
                    records["agents"][0],
                    records["sessions"][0],
                ),
                public_request_id=public_id,
                provider="ollama",
                model="llama3.2:3b",
                worker_id="worker-second",
                db=db,
            )

        db.rollback()

    with SessionLocal() as db:
        saved = db.execute(
            select(AgentRequest).where(
                AgentRequest.tenant_id
                == records["tenants"][0],
                AgentRequest.public_request_id
                == public_id,
            )
        ).scalars().all()

        assert len(saved) == 1
        assert saved[0].lease_token == first.lease_token
        assert saved[0].lease_owner_id == "worker-first"
