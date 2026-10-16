
"""Real PostgreSQL tests for public request ID persistence."""

import os
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.contracts import TrustedIdentityContext
from app.gateway.postgres_request_lifecycle import start_request
from app.infrastructure.database import DATABASE_URL, SessionLocal
from app.infrastructure.models import (
    Agent,
    AgentRequest,
    AgentSession,
    Tenant,
)
from app.infrastructure.persistence import create_request


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_POSTGRES_INTEGRATION") != "1",
    reason="PostgreSQL integration tests disabled.",
)


def verify_test_database():
    if (
        os.getenv("DB_NAME") != "aegistwin_test_db"
        or DATABASE_URL.database != "aegistwin_test_db"
        or DATABASE_URL.host not in ("localhost", "127.0.0.1")
        or DATABASE_URL.port not in (55432, 55433)
    ):
        raise RuntimeError("Unsafe PostgreSQL test database.")


@pytest.fixture
def records():
    """Create isolated records and remove them after every test."""
    verify_test_database()

    from sqlalchemy import delete

    tenant_ids = []
    agent_ids = []
    session_ids = []

    try:
        with SessionLocal() as db:
            tenants = [
                Tenant(name=f"PublicID-{uuid4().hex}"),
                Tenant(name=f"PublicID-{uuid4().hex}"),
            ]
            db.add_all(tenants)
            db.flush()
            tenant_ids = [tenant.id for tenant in tenants]

            agents = [
                Agent(tenant_id=tenants[0].id, name="Agent A"),
                Agent(tenant_id=tenants[1].id, name="Agent B"),
            ]
            db.add_all(agents)
            db.flush()
            agent_ids = [agent.id for agent in agents]

            sessions = [
                AgentSession(
                    tenant_id=tenants[0].id,
                    agent_id=agents[0].id,
                ),
                AgentSession(
                    tenant_id=tenants[1].id,
                    agent_id=agents[1].id,
                ),
            ]
            db.add_all(sessions)
            db.flush()
            session_ids = [session.id for session in sessions]

            data = [
                (tenants[0].id, agents[0].id, sessions[0].id),
                (tenants[1].id, agents[1].id, sessions[1].id),
            ]
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


def make_request(tenant_data, public_id):
    tenant_id, agent_id, session_id = tenant_data

    return create_request(
        tenant_id=tenant_id,
        agent_id=agent_id,
        session_id=session_id,
        provider="test",
        model="test-model",
        public_request_id=public_id,
    )


def test_public_id_survives_commit(records):
    public_id = f"REQ-{uuid4().hex[:12]}"

    request_id = make_request(records[0], public_id)

    with SessionLocal() as db:
        saved = db.get(AgentRequest, request_id)
        assert saved is not None
        assert saved.public_request_id == public_id


def test_duplicate_id_same_tenant_rejected(records):
    public_id = f"REQ-{uuid4().hex[:12]}"

    make_request(records[0], public_id)

    with pytest.raises(IntegrityError):
        make_request(records[0], public_id)


def test_same_id_different_tenants_allowed(records):
    public_id = f"REQ-{uuid4().hex[:12]}"

    first = make_request(records[0], public_id)
    second = make_request(records[1], public_id)

    assert first != second

    with SessionLocal() as db:
        matching = db.execute(
            select(AgentRequest).where(
                AgentRequest.public_request_id == public_id
            )
        ).scalars().all()

        assert len(matching) == 2


def test_null_public_ids_allowed(records):
    first = make_request(records[0], None)
    second = make_request(records[0], None)

    assert first != second


def test_gateway_start_request_persists_public_id(records):
    tenant_id, agent_id, session_id = records[0]
    public_id = f"REQ-{uuid4().hex[:12]}"

    identity = TrustedIdentityContext(
        tenant_id=str(tenant_id),
        agent_id=str(agent_id),
        session_id=str(session_id),
        user_id="test-user",
    )

    with SessionLocal() as db:
        result = start_request(
            identity=identity,
            public_request_id=public_id,
            provider="test",
            model="test-model",
            db=db,
        )
        db.commit()

    with SessionLocal() as db:
        saved = db.get(AgentRequest, result.request_id)

        assert saved is not None
        assert saved.public_request_id == public_id
        assert saved.tenant_id == tenant_id
        assert saved.status == "pending"
