
"""Security tests for PostgreSQL session ownership resolution."""

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.contracts import TrustedIdentityContext
from app.gateway.postgres_session_resolver import (
    InvalidDatabaseIdentity,
    SessionAccessDenied,
    resolve_existing_session,
)


def make_identity(tenant_id, agent_id, session_id):
    return TrustedIdentityContext(
        tenant_id=str(tenant_id),
        user_id="test-user",
        agent_id=str(agent_id),
        session_id=str(session_id),
    )


def make_db(agent_exists=True, session_exists=True):
    db = MagicMock()

    agent_result = MagicMock()
    agent_result.scalar_one_or_none.return_value = (
        object() if agent_exists else None
    )

    session_result = MagicMock()
    session_result.scalar_one_or_none.return_value = (
        object() if session_exists else None
    )

    db.execute.side_effect = [
        agent_result,
        session_result,
    ]

    return db


def test_valid_session_is_accepted():
    tenant_id = uuid4()
    agent_id = uuid4()
    session_id = uuid4()

    db = make_db()

    result = resolve_existing_session(
        make_identity(tenant_id, agent_id, session_id),
        db,
    )

    assert result.tenant_id == tenant_id
    assert result.agent_id == agent_id
    assert result.session_id == session_id
    assert db.execute.call_count == 2


def test_foreign_tenant_is_rejected():
    db = make_db(agent_exists=False)

    with pytest.raises(SessionAccessDenied):
        resolve_existing_session(
            make_identity(uuid4(), uuid4(), uuid4()),
            db,
        )

    assert db.execute.call_count == 1


def test_foreign_agent_is_rejected():
    db = make_db(session_exists=False)

    with pytest.raises(SessionAccessDenied):
        resolve_existing_session(
            make_identity(uuid4(), uuid4(), uuid4()),
            db,
        )

    assert db.execute.call_count == 2


def test_unknown_or_ended_session_is_rejected():
    db = make_db(session_exists=False)

    with pytest.raises(SessionAccessDenied):
        resolve_existing_session(
            make_identity(uuid4(), uuid4(), uuid4()),
            db,
        )


def test_malformed_uuid_is_rejected():
    db = MagicMock()

    with pytest.raises(InvalidDatabaseIdentity):
        resolve_existing_session(
            make_identity("tenant-test", uuid4(), uuid4()),
            db,
        )

    db.execute.assert_not_called()
