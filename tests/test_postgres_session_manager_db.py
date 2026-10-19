
"""Real PostgreSQL tests for runtime session management."""

import os
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.contracts import TrustedIdentityContext
from app.gateway.postgres_session_manager import (
    manage_postgres_session,
)
from app.gateway.postgres_session_resolver import (
    SessionAccessDenied,
)


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
        or DATABASE_URL.host not in ("127.0.0.1", "localhost")
        or DATABASE_URL.port not in (55432, 55433)
    ):
        raise RuntimeError("Unsafe database connection.")


def make_identity(tenant_id, agent_id, session_id="SES-legacy"):
    return TrustedIdentityContext(
        tenant_id=str(tenant_id),
        agent_id=str(agent_id),
        user_id="test-user",
        session_id=str(session_id),
    )


@pytest.fixture
def records():
    """Create temporary data within a rollback-only transaction."""
    verify_test_database()

    from app.infrastructure.database import SessionLocal
    from app.infrastructure.models import (
        Tenant,
        Agent,
        AgentSession,
    )

    with SessionLocal() as db:
        try:
            tenant_a = Tenant(name=f"Session Test A {uuid4().hex}")
            tenant_b = Tenant(name=f"Session Test B {uuid4().hex}")

            db.add_all([tenant_a, tenant_b])
            db.flush()

            agent_a = Agent(
                tenant_id=tenant_a.id,
                name="Agent A",
            )
            agent_b = Agent(
                tenant_id=tenant_a.id,
                name="Agent B",
            )
            foreign_agent = Agent(
                tenant_id=tenant_b.id,
                name="Foreign Agent",
            )

            db.add_all([agent_a, agent_b, foreign_agent])
            db.flush()

            active_session = AgentSession(
                tenant_id=tenant_a.id,
                agent_id=agent_a.id,
            )
            ended_session = AgentSession(
                tenant_id=tenant_a.id,
                agent_id=agent_a.id,
                ended_at=datetime.now(timezone.utc),
            )

            db.add_all([active_session, ended_session])
            db.flush()

            yield {
                "db": db,
                "tenant_a": tenant_a.id,
                "tenant_b": tenant_b.id,
                "agent_a": agent_a.id,
                "agent_b": agent_b.id,
                "foreign_agent": foreign_agent.id,
                "active_session": active_session.id,
                "ended_session": ended_session.id,
            }
        finally:
            db.rollback()


def test_authorized_agent_creates_session(records):
    data = records

    result = manage_postgres_session(
        identity=make_identity(
            data["tenant_a"],
            data["agent_a"],
        ),
        db=data["db"],
        requested_session_id=None,
    )

    assert result.created is True
    assert result.identity.session_id == str(result.session_id)

    from app.infrastructure.models import AgentSession

    saved = data["db"].get(AgentSession, result.session_id)

    assert saved is not None
    assert saved.tenant_id == data["tenant_a"]
    assert saved.agent_id == data["agent_a"]


def test_existing_session_reused(records):
    data = records

    result = manage_postgres_session(
        identity=make_identity(
            data["tenant_a"],
            data["agent_a"],
        ),
        db=data["db"],
        requested_session_id=str(data["active_session"]),
    )

    assert result.created is False
    assert result.session_id == data["active_session"]


def test_foreign_tenant_cannot_reuse_session(records):
    data = records

    with pytest.raises(SessionAccessDenied):
        manage_postgres_session(
            identity=make_identity(
                data["tenant_b"],
                data["foreign_agent"],
            ),
            db=data["db"],
            requested_session_id=str(data["active_session"]),
        )


def test_other_agent_cannot_reuse_session(records):
    data = records

    with pytest.raises(SessionAccessDenied):
        manage_postgres_session(
            identity=make_identity(
                data["tenant_a"],
                data["agent_b"],
            ),
            db=data["db"],
            requested_session_id=str(data["active_session"]),
        )


def test_ended_session_cannot_be_reused(records):
    data = records

    with pytest.raises(SessionAccessDenied):
        manage_postgres_session(
            identity=make_identity(
                data["tenant_a"],
                data["agent_a"],
            ),
            db=data["db"],
            requested_session_id=str(data["ended_session"]),
        )


def test_foreign_agent_cannot_create_session(records):
    data = records

    with pytest.raises(SessionAccessDenied):
        manage_postgres_session(
            identity=make_identity(
                data["tenant_a"],
                data["foreign_agent"],
            ),
            db=data["db"],
            requested_session_id=None,
        )
