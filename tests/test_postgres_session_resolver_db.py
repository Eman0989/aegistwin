
"""Real PostgreSQL tests for gateway session authorization."""

import os
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.contracts import TrustedIdentityContext
from app.gateway.postgres_session_resolver import (
    SessionAccessDenied,
    resolve_existing_session,
)


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_POSTGRES_INTEGRATION") != "1",
    reason="Real PostgreSQL integration tests are disabled.",
)


def verify_test_database():
    """Prevent tests from touching non-test databases."""

    if os.getenv("DB_NAME") != "aegistwin_test_db":
        raise RuntimeError("Refusing to use a non-test database.")

    from app.infrastructure.database import DATABASE_URL

    if (
        DATABASE_URL.database != "aegistwin_test_db"
        or DATABASE_URL.host not in ("localhost", "127.0.0.1")
        or DATABASE_URL.port not in (55432, 55433)
    ):
        raise RuntimeError("Unsafe PostgreSQL connection.")


def make_identity(tenant_id, agent_id, session_id):
    return TrustedIdentityContext(
        tenant_id=str(tenant_id),
        user_id="database-test-user",
        agent_id=str(agent_id),
        session_id=str(session_id),
        permissions={"model:generate"},
        credential_source="test",
    )


@pytest.fixture
def database_records():
    """Create temporary database records and roll them back."""

    verify_test_database()

    from app.infrastructure.database import SessionLocal
    from app.infrastructure.models import (
        Tenant,
        Agent,
        AgentSession,
    )

    with SessionLocal() as db:
        try:
            tenant_a = Tenant(name=f"Test Tenant A {uuid4().hex[:8]}")
            tenant_b = Tenant(name=f"Test Tenant B {uuid4().hex[:8]}")

            db.add_all([tenant_a, tenant_b])
            db.flush()

            agent_a = Agent(
                tenant_id=tenant_a.id,
                name="Test Agent A",
            )

            agent_b = Agent(
                tenant_id=tenant_a.id,
                name="Test Agent B",
            )

            agent_other = Agent(
                tenant_id=tenant_b.id,
                name="Test Agent Other",
            )

            db.add_all([agent_a, agent_b, agent_other])
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
                "agent_other": agent_other.id,
                "active_session": active_session.id,
                "ended_session": ended_session.id,
            }

        finally:
            # No fixture records are committed.
            db.rollback()


def test_valid_session_allowed(database_records):
    data = database_records

    result = resolve_existing_session(
        make_identity(
            data["tenant_a"],
            data["agent_a"],
            data["active_session"],
        ),
        data["db"],
    )

    assert result.tenant_id == data["tenant_a"]
    assert result.agent_id == data["agent_a"]
    assert result.session_id == data["active_session"]


def test_cross_tenant_access_denied(database_records):
    data = database_records

    with pytest.raises(SessionAccessDenied):
        resolve_existing_session(
            make_identity(
                data["tenant_b"],
                data["agent_a"],
                data["active_session"],
            ),
            data["db"],
        )


def test_cross_agent_access_denied(database_records):
    data = database_records

    with pytest.raises(SessionAccessDenied):
        resolve_existing_session(
            make_identity(
                data["tenant_a"],
                data["agent_b"],
                data["active_session"],
            ),
            data["db"],
        )


def test_ended_session_denied(database_records):
    data = database_records

    with pytest.raises(SessionAccessDenied):
        resolve_existing_session(
            make_identity(
                data["tenant_a"],
                data["agent_a"],
                data["ended_session"],
            ),
            data["db"],
        )


def test_unknown_session_denied(database_records):
    data = database_records

    with pytest.raises(SessionAccessDenied):
        resolve_existing_session(
            make_identity(
                data["tenant_a"],
                data["agent_a"],
                uuid4(),
            ),
            data["db"],
        )
