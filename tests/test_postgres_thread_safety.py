
"""Thread-safety and cancellation regression tests for PostgreSQL."""

import asyncio
import threading
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.contracts import ModelRequest, TrustedIdentityContext
from app.gateway.postgres_orchestrator import (
    _prepare_with_session_factory,
    run_postgres_inference,
)
from app.gateway.postgres_request_lifecycle import PersistedRequest
from app.gateway.postgres_session_manager import ManagedSession


def make_request():
    return ModelRequest(
        request_id="REQ-thread-safety-test",
        provider="ollama",
        model="test-model",
        messages=[{"role": "user", "content": "Hello"}],
        trusted_context=TrustedIdentityContext(
            tenant_id=str(uuid4()),
            agent_id=str(uuid4()),
            user_id="test-user",
            session_id="SES-temporary",
        ),
    )


def make_database_setup(request):
    session_id = uuid4()

    managed = ManagedSession(
        identity=request.trusted_context.model_copy(
            update={"session_id": str(session_id)}
        ),
        session_id=session_id,
        created=True,
    )

    persisted = PersistedRequest(
        request_id=uuid4(),
        tenant_id=uuid4(),
        agent_id=uuid4(),
        session_id=session_id,
        public_request_id=request.request_id,
        lease_token="test-lease-token",
    )

    return managed, persisted


def test_session_factory_closes_session_after_commit():
    """A successful transaction must close its database session."""
    request = make_request()
    managed, persisted = make_database_setup(request)

    db = MagicMock()
    factory = MagicMock()

    factory.return_value.__enter__.return_value = db

    with (
        patch(
            "app.gateway.postgres_orchestrator.manage_postgres_session",
            return_value=managed,
        ),
        patch(
            "app.gateway.postgres_orchestrator.start_leased_request",
            return_value=persisted,
        ),
    ):
        result = _prepare_with_session_factory(
            model_request=request,
            requested_session_id=None,
            worker_id="worker-test",
            session_factory=factory,
        )

    assert result[0] == managed
    assert result[2] == persisted

    factory.assert_called_once()
    factory.return_value.__exit__.assert_called_once()

    db.commit.assert_called_once()
    db.rollback.assert_not_called()


def test_session_factory_closes_session_after_failed_commit():
    """A failed commit must roll back and close the session."""
    request = make_request()
    managed, persisted = make_database_setup(request)

    db = MagicMock()
    db.commit.side_effect = RuntimeError("Simulated commit failure")

    factory = MagicMock()
    factory.return_value.__enter__.return_value = db

    with (
        patch(
            "app.gateway.postgres_orchestrator.manage_postgres_session",
            return_value=managed,
        ),
        patch(
            "app.gateway.postgres_orchestrator.start_leased_request",
            return_value=persisted,
        ),
    ):
        with pytest.raises(RuntimeError, match="commit failure"):
            _prepare_with_session_factory(
                model_request=request,
                requested_session_id=None,
                worker_id="worker-test",
                session_factory=factory,
            )

    db.commit.assert_called_once()
    db.rollback.assert_called_once()
    factory.return_value.__exit__.assert_called_once()


@pytest.mark.asyncio
async def test_cancellation_during_initial_commit_never_starts_provider():
    """Cancelling inference must not start provider work after commit."""
    request = make_request()
    managed, persisted = make_database_setup(request)

    commit_started = threading.Event()
    release_commit = threading.Event()
    commit_finished = threading.Event()

    db = MagicMock()

    def slow_commit():
        commit_started.set()
        try:
            if not release_commit.wait(timeout=5):
                raise TimeoutError("Test commit was not released")
        finally:
            commit_finished.set()

    db.commit.side_effect = slow_commit

    factory = MagicMock()
    factory.return_value.__enter__.return_value = db

    provider = MagicMock()
    provider.generate = AsyncMock()

    with (
        patch(
            "app.gateway.postgres_orchestrator.manage_postgres_session",
            return_value=managed,
        ),
        patch(
            "app.gateway.postgres_orchestrator.start_leased_request",
            return_value=persisted,
        ),
    ):
        task = asyncio.create_task(
            run_postgres_inference(
                model_request=request,
                provider_router=provider,
                session_factory=factory,
                requested_session_id=None,
            )
        )

        try:
            started = await asyncio.to_thread(
                commit_started.wait, 2
            )
            assert started, "Commit did not begin"

            task.cancel()

            with pytest.raises(asyncio.CancelledError):
                await task

        finally:
            release_commit.set()

            assert await asyncio.to_thread(
                commit_finished.wait, 2
            ), "Database worker did not finish"

    provider.generate.assert_not_awaited()


@pytest.mark.asyncio
async def test_cancellation_during_audit_never_returns_model_output():
    """Cancelled requests must not release unaudited model output."""
    request = make_request()
    managed, persisted = make_database_setup(request)

    audit_started = threading.Event()
    release_audit = threading.Event()
    audit_finished = threading.Event()

    def slow_finalization(**kwargs):
        audit_started.set()

        try:
            if not release_audit.wait(timeout=5):
                raise TimeoutError("Test audit was not released")

            return persisted.request_id
        finally:
            audit_finished.set()

    db = MagicMock()

    provider = MagicMock()
    provider.generate = AsyncMock()

    # Create a provider response without an actual network request.
    from app.contracts import ModelResponse

    provider.generate.return_value = ModelResponse(
        request_id=request.request_id,
        provider=request.provider,
        model=request.model,
        content="Safe model response",
        usage={"input_tokens": 1, "output_tokens": 2},
        latency_ms=10.0,
    )

    from app.security.llm_response_inspector import (
        ResponseAction,
        ResponseInspection,
    )

    with (
        patch(
            "app.gateway.postgres_orchestrator.manage_postgres_session",
            return_value=managed,
        ),
        patch(
            "app.gateway.postgres_orchestrator.start_leased_request",
            return_value=persisted,
        ),
        patch(
            "app.gateway.postgres_orchestrator.finish_request",
            side_effect=slow_finalization,
        ),
        patch(
            "app.gateway.postgres_orchestrator.inspect_response",
            return_value=ResponseInspection(
                action=ResponseAction.ALLOW,
                content="Safe model response",
                reason="Safe",
            ),
        ),
    ):
        task = asyncio.create_task(
            run_postgres_inference(
                model_request=request,
                provider_router=provider,
                db=db,
                requested_session_id=None,
            )
        )

        try:
            started = await asyncio.to_thread(
                audit_started.wait, 2
            )
            assert started, "Audit finalization did not begin"

            task.cancel()

            with pytest.raises(asyncio.CancelledError):
                await task

        finally:
            release_audit.set()

            assert await asyncio.to_thread(
                audit_finished.wait, 2
            ), "Audit worker did not finish"

    provider.generate.assert_awaited_once()
    assert task.cancelled()


@pytest.mark.asyncio
async def test_provider_cancellation_does_not_finalize_success():
    """Cancelling provider inference must never finalize as completed."""
    request = make_request()
    managed, persisted = make_database_setup(request)

    provider_started = asyncio.Event()

    async def slow_provider(_request):
        provider_started.set()
        await asyncio.Event().wait()

    provider = MagicMock()
    provider.generate = AsyncMock(side_effect=slow_provider)

    db = MagicMock()

    with (
        patch(
            "app.gateway.postgres_orchestrator.manage_postgres_session",
            return_value=managed,
        ),
        patch(
            "app.gateway.postgres_orchestrator.start_leased_request",
            return_value=persisted,
        ),
        patch(
            "app.gateway.postgres_orchestrator.finish_request"
        ) as mock_finish,
    ):
        task = asyncio.create_task(
            run_postgres_inference(
                model_request=request,
                provider_router=provider,
                db=db,
                requested_session_id=None,
            )
        )

        try:
            await asyncio.wait_for(
                provider_started.wait(), timeout=2
            )

            task.cancel()

            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(task, timeout=2)

        finally:
            if not task.done():
                task.cancel()

        mock_finish.assert_not_called()
