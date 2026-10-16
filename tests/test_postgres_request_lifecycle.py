
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
    RequestFinalizationError,
    attach_lease,
    finish_request,
    start_request,
)


# ==========================================================
# TEST HELPERS
# ==========================================================


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


# ==========================================================
# REQUEST CREATION
# ==========================================================


@patch(
    "app.gateway.postgres_request_lifecycle.resolve_existing_session"
)
def test_start_request(mock_resolve):
    resolved = ResolvedSession(
        tenant_id=uuid4(),
        agent_id=uuid4(),
        session_id=uuid4(),
    )

    mock_resolve.return_value = resolved

    db = MagicMock()

    # Simulate SQLAlchemy assigning a UUID during flush.
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

    # Verify the public ID reaches the SQLAlchemy model.
    assert inserted.public_request_id == "REQ-test123"

    db.flush.assert_called_once()
    db.commit.assert_not_called()


@patch(
    "app.gateway.postgres_request_lifecycle.resolve_existing_session"
)
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


# ==========================================================
# SUCCESSFUL FINALIZATION
# ==========================================================


@patch(
    "app.gateway.postgres_request_lifecycle.complete_request"
)
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


# ==========================================================
# PROVIDER FAILURE
# ==========================================================


@patch(
    "app.gateway.postgres_request_lifecycle.complete_request"
)
def test_provider_failure(mock_complete):
    request = make_request()

    # The database must return the finalized request UUID.
    mock_complete.return_value = request.request_id

    result = finish_request(
        request=request,
        outcome="failed",
        error_code="provider_unavailable",
    )

    assert result == request.request_id

    assert (
        mock_complete.call_args.kwargs["error_code"]
        == "provider_unavailable"
    )

    assert (
        mock_complete.call_args.kwargs["status"]
        == "failed"
    )


# ==========================================================
# BLOCKED RESPONSE
# ==========================================================


@patch(
    "app.gateway.postgres_request_lifecycle.complete_request"
)
def test_blocked_response(mock_complete):
    request = make_request()

    # The database must return the finalized request UUID.
    mock_complete.return_value = request.request_id

    result = finish_request(
        request=request,
        outcome="blocked",
    )

    assert result == request.request_id

    assert (
        mock_complete.call_args.kwargs["status"]
        == "blocked"
    )

    assert (
        mock_complete.call_args.kwargs["error_code"]
        == "response_blocked"
    )


# ==========================================================
# INVALID STATUS
# ==========================================================


@patch(
    "app.gateway.postgres_request_lifecycle.complete_request"
)
def test_invalid_status_rejected(mock_complete):
    with pytest.raises(ValueError):
        finish_request(
            request=make_request(),
            outcome="arbitrary_status",
        )

    mock_complete.assert_not_called()


# ==========================================================
# SECURITY: REJECTED AUDIT FINALIZATION
# ==========================================================


@patch(
    "app.gateway.postgres_request_lifecycle.complete_request"
)
def test_rejected_finalization_fails_closed(mock_complete):
    request = make_request()

    # PostgreSQL rejected the conditional update.
    mock_complete.return_value = None

    with pytest.raises(
        RequestFinalizationError,
        match="finalization was rejected",
    ):
        finish_request(
            request=request,
            outcome="completed",
        )

    mock_complete.assert_called_once()


# ==========================================================
# SECURITY: INCORRECT DATABASE RESPONSE
# ==========================================================


@patch(
    "app.gateway.postgres_request_lifecycle.complete_request"
)
def test_unexpected_finalization_id_rejected(mock_complete):
    request = make_request()

    # Simulate an unexpected database return value.
    mock_complete.return_value = uuid4()

    with pytest.raises(
        RequestFinalizationError,
        match="unexpected ID",
    ):
        finish_request(
            request=request,
            outcome="completed",
        )

    mock_complete.assert_called_once()


# ==========================================================
# SECURITY: LEASE TOKEN FORWARDING
# ==========================================================


@patch(
    "app.gateway.postgres_request_lifecycle.complete_request"
)
def test_leased_request_passes_token(mock_complete):
    request = make_request()
    token = uuid4().hex

    leased_request = attach_lease(
        request=request,
        lease_token=token,
    )

    # Attaching a lease must not mutate the original request.
    assert request.lease_token is None
    assert leased_request.lease_token == token

    mock_complete.return_value = request.request_id

    result = finish_request(
        request=leased_request,
        outcome="completed",
    )

    assert result == request.request_id

    assert (
        mock_complete.call_args.kwargs["lease_token"]
        == token
    )

    assert (
        mock_complete.call_args.kwargs["request_id"]
        == request.request_id
    )
