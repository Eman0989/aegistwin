
"""Regression test for blocking DB work in async inference."""

import asyncio
import time
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.contracts import (
    ModelRequest,
    ModelResponse,
    TrustedIdentityContext,
)
from app.gateway.postgres_orchestrator import run_postgres_inference
from app.gateway.postgres_request_lifecycle import PersistedRequest
from app.gateway.postgres_session_manager import ManagedSession
from app.security.llm_response_inspector import (
    ResponseAction,
    ResponseInspection,
)


@pytest.mark.asyncio
async def test_slow_database_commit_does_not_block_event_loop():
    request = ModelRequest(
        request_id="REQ-EVENT-LOOP-001",
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

    response = ModelResponse(
        request_id=request.request_id,
        provider=request.provider,
        model=request.model,
        content="Safe response",
        usage={"input_tokens": 2, "output_tokens": 3},
        latency_ms=10.0,
    )

    db = MagicMock()

    commit_started = asyncio.Event()
    ticker_ran = asyncio.Event()

    def slow_commit():
        # Simulate a slow synchronous PostgreSQL commit.
        time.sleep(0.2)

    db.commit.side_effect = slow_commit

    async def ticker():
        await asyncio.sleep(0.02)
        ticker_ran.set()

    async def generate(_request):
        # Provider inference should begin only after commit.
        assert ticker_ran.is_set(), (
            "Synchronous database work blocked the event loop"
        )
        return response

    provider = MagicMock()
    provider.generate = AsyncMock(side_effect=generate)

    @asynccontextmanager
    async def fake_heartbeat(*args, **kwargs):
        yield asyncio.Event()

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
            return_value=persisted.request_id,
        ),
        patch(
            "app.gateway.postgres_orchestrator._lease_heartbeat",
            side_effect=fake_heartbeat,
        ),
        patch(
            "app.gateway.postgres_orchestrator.inspect_response",
            return_value=ResponseInspection(
                action=ResponseAction.ALLOW,
                content="Safe response",
                reason="Safe",
            ),
        ),
    ):
        ticker_task = asyncio.create_task(ticker())

        try:
            result = await run_postgres_inference(
                model_request=request,
                provider_router=provider,
                db=db,
                requested_session_id=None,
            )
            assert result.response.content == "Safe response"
        finally:
            await ticker_task

    db.commit.assert_called_once()
    provider.generate.assert_awaited_once()
