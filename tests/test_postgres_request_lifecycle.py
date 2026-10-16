
"""Tests for the gateway PostgreSQL request lifecycle."""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.contracts import TrustedIdentityContext
from app.gateway.postgres_session_resolver import (
    ResolvedSession,
    SessionAccessDenied,
)
from app.gateway.postgres_request_lifecycle import (
    PersistedRequest,
    finish_request,
    start_request,
)


def make_identity():
    return TrustedIdentityContext(
        tenant_id=str(uuid4()),
        user_id="test-user",
        agent_id=str(uuid4()),
        session_id=str(uuid4()),
    )


def make_request():
    return PersistedRequest(
        request_id=uuid4(),
        tenant_id=uuid4(),
        agent_id=uuid4(),
        session_id=uuid4(),
        public_request_id="REQ-test123",
    )



@patch("app.gateway.postgres_request_lifecycle.resolve_existing_session")
def test_start_request(mock_resolve):
    resolved = ResolvedSession(
        tenant_id=uuid4(),
        agent_id=uuid4(),
        session_id=uuid4(),
    )
    mock_resolve.return_value = resolved

    db = MagicMock()

    # Simulate SQLAlchemy assigning the UUID during flush.
    def assign_request_id():
        database_request = db.add.call_args.args[0]
        database_request.id = uuid4()

    db.flush.side_effect = assign_request_id

    result = start_request(
        identity=make_identity(),
        public_request_id="REQ-test123",
        provider="ollama",
        model="llama3.2:3b",
        db=db,
    )

    assert result.tenant_id == resolved.tenant_id
    assert result.agent_id == resolved.agent_id
    assert result.session_id == resolved.session_id
    assert result.public_request_id == "REQ-test123"

    inserted = db.add.call_args.args[0]

    assert inserted.id == result.request_id
    assert inserted.tenant_id == resolved.tenant_id
    assert inserted.agent_id == resolved.agent_id
    assert inserted.session_id == resolved.session_id
    assert inserted.provider == "ollama"
    assert inserted.model == "llama3.2:3b"
    assert inserted.status == "pending"

    db.flush.assert_called_once()
    db.commit.assert_not_called()


@patch("app.gateway.postgres_request_lifecycle.resolve_existing_session")
def test_unauthorized_request_rejected(mock_resolve):
    mock_resolve.side_effect = SessionAccessDenied(
        "Session is not authorized."
    )

    db = MagicMock()

    with pytest.raises(SessionAccessDenied):
        start_request(
            identity=make_identity(),
            public_request_id="REQ-test123",
            provider="ollama",
            model="llama3.2:3b",
            db=db,
        )

    db.add.assert_not_called()
    db.flush.assert_not_called()
    db.commit.assert_not_called()



@patch("app.gateway.postgres_request_lifecycle.complete_request")
def test_successful_completion(mock_complete):
    request = make_request()
    mock_complete.return_value = request.request_id

    result = finish_request(
        request=request,
        outcome="completed",
        latency_ms=120.5,
        input_tokens=30,
        output_tokens=45,
    )

    assert result == request.request_id
    mock_complete.assert_called_once_with(
        request_id=request.request_id,
        tenant_id=request.tenant_id,
        status="completed",
        latency=120.5,
        input_tokens=30,
        output_tokens=45,
        error_code=None,
    )


@patch("app.gateway.postgres_request_lifecycle.complete_request")
def test_provider_failure(mock_complete):
    request = make_request()

    finish_request(
        request=request,
        outcome="failed",
        error_code="provider_unavailable",
    )

    assert (
        mock_complete.call_args.kwargs["error_code"]
        == "provider_unavailable"
    )


@patch("app.gateway.postgres_request_lifecycle.complete_request")
def test_blocked_response(mock_complete):
    request = make_request()

    finish_request(
        request=request,
        outcome="blocked",
    )

    assert mock_complete.call_args.kwargs["status"] == "blocked"
    assert (
        mock_complete.call_args.kwargs["error_code"]
        == "response_blocked"
    )


@patch("app.gateway.postgres_request_lifecycle.complete_request")
def test_invalid_status_rejected(mock_complete):
    with pytest.raises(ValueError):
        finish_request(
            request=make_request(),
            outcome="arbitrary_status",
        )

    mock_complete.assert_not_called()
