
"""Unit tests for PostgreSQL-backed runtime sessions."""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.contracts import TrustedIdentityContext
from app.gateway.postgres_session_resolver import (
    InvalidDatabaseIdentity,
    ResolvedSession,
    SessionAccessDenied,
)
from app.gateway.postgres_session_manager import (
    manage_postgres_session,
)


def make_identity(
    tenant_id=None,
    agent_id=None,
    session_id="SES-legacy",
):
    return TrustedIdentityContext(
        tenant_id=str(tenant_id or uuid4()),
        user_id="test-user",
        agent_id=str(agent_id or uuid4()),
        session_id=session_id,
    )


def test_new_session_created_for_authorized_agent():
    db = MagicMock()
    db.execute.return_value.scalar_one_or_none.return_value = object()

    def assign_uuid():
        session = db.add.call_args.args[0]
        session.id = uuid4()

    db.flush.side_effect = assign_uuid

    result = manage_postgres_session(
        identity=make_identity(),
        db=db,
        requested_session_id=None,
    )

    assert result.created is True
    assert result.identity.session_id == str(result.session_id)
    assert result.session_id is not None
    db.add.assert_called_once()
    db.flush.assert_called_once()
    db.commit.assert_not_called()


@patch(
    "app.gateway.postgres_session_manager.resolve_existing_session"
)
def test_existing_session_reused(mock_resolve):
    session_id = uuid4()

    mock_resolve.return_value = ResolvedSession(
        tenant_id=uuid4(),
        agent_id=uuid4(),
        session_id=session_id,
    )

    db = MagicMock()

    result = manage_postgres_session(
        identity=make_identity(),
        db=db,
        requested_session_id=str(session_id),
    )

    assert result.created is False
    assert result.session_id == session_id
    assert result.identity.session_id == str(session_id)
    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_foreign_agent_cannot_create_session():
    db = MagicMock()
    db.execute.return_value.scalar_one_or_none.return_value = None

    with pytest.raises(SessionAccessDenied):
        manage_postgres_session(
            identity=make_identity(),
            db=db,
            requested_session_id=None,
        )

    db.add.assert_not_called()
    db.flush.assert_not_called()


@patch(
    "app.gateway.postgres_session_manager.resolve_existing_session"
)
def test_foreign_session_rejected(mock_resolve):
    mock_resolve.side_effect = SessionAccessDenied(
        "Session is not authorized."
    )

    db = MagicMock()

    with pytest.raises(SessionAccessDenied):
        manage_postgres_session(
            identity=make_identity(),
            db=db,
            requested_session_id=str(uuid4()),
        )

    db.add.assert_not_called()


def test_malformed_session_uuid_rejected():
    db = MagicMock()

    with pytest.raises(InvalidDatabaseIdentity):
        manage_postgres_session(
            identity=make_identity(),
            db=db,
            requested_session_id="SES-not-a-uuid",
        )

    db.execute.assert_not_called()


def test_new_session_does_not_commit():
    db = MagicMock()
    db.execute.return_value.scalar_one_or_none.return_value = object()

    def assign_uuid():
        db.add.call_args.args[0].id = uuid4()

    db.flush.side_effect = assign_uuid

    manage_postgres_session(
        identity=make_identity(),
        db=db,
        requested_session_id=None,
    )

    db.commit.assert_not_called()
