
"""HTTP client-disconnect regression tests for AegisTwin."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from starlette.requests import Request

from app.contracts import ModelResponse
from app.gateway.routes import (
    RuntimeModelRequest,
    generate_model,
)
from app.gateway.postgres_orchestrator import OrchestrationResult


@pytest.mark.asyncio
async def test_postgres_disconnect_cancels_inference():
    """Disconnecting the client should stop unnecessary inference."""

    disconnect_event = asyncio.Event()
    provider_started = asyncio.Event()
    provider_cancelled = asyncio.Event()

    async def receive():
        await disconnect_event.wait()
        return {"type": "http.disconnect"}

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/v1/model/generate",
        "headers": [],
        "query_string": b"",
        "http_version": "1.1",
        "scheme": "http",
        "server": ("testserver", 80),
        "client": ("127.0.0.1", 50000),
    }

    http_request = Request(scope, receive=receive)

    from fastapi import Response
    from app.contracts import TrustedIdentityContext

    identity = TrustedIdentityContext(
        tenant_id=str(uuid4()),
        agent_id=str(uuid4()),
        user_id="test-user",
        session_id="SES-temporary",
    )

    model_request = RuntimeModelRequest(
        provider="ollama",
        model="test-model",
        messages=[{"role": "user", "content": "Hello"}],
    )

    provider = MagicMock()
    provider.generate = AsyncMock()

    async def fake_postgres(**kwargs):
        provider_started.set()

        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            provider_cancelled.set()
            raise

    with (
        patch(
            "app.gateway.routes.postgres_runtime_enabled",
            return_value=True,
        ),
        patch(
            "app.gateway.routes.generate_postgres_response",
            side_effect=fake_postgres,
        ),
    ):
        task = asyncio.create_task(
            generate_model(
                request=model_request,
                http_request=http_request,
                http_response=Response(),
                identity=identity,
                provider_router=provider,
            )
        )

        try:
            await asyncio.wait_for(
                provider_started.wait(),
                timeout=2,
            )

            disconnect_event.set()

            await asyncio.wait_for(
                provider_cancelled.wait(),
                timeout=2,
            )

            with pytest.raises(asyncio.CancelledError):
                await task

        finally:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

@pytest.mark.asyncio
async def test_completed_inference_wins_simultaneous_disconnect():
    """Completed audited inference must not be discarded in a race."""
    from fastapi import Response
    from app.contracts import TrustedIdentityContext

    disconnect_event = asyncio.Event()
    started = asyncio.Event()
    release = asyncio.Event()

    async def receive():
        await disconnect_event.wait()
        return {"type": "http.disconnect"}

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/v1/model/generate",
        "headers": [],
        "query_string": b"",
        "http_version": "1.1",
        "scheme": "http",
        "server": ("testserver", 80),
        "client": ("127.0.0.1", 50000),
    }

    http_request = Request(scope, receive=receive)

    identity = TrustedIdentityContext(
        tenant_id=str(uuid4()),
        agent_id=str(uuid4()),
        user_id="test-user",
        session_id="SES-temporary",
    )

    model_request = RuntimeModelRequest(
        provider="ollama",
        model="test-model",
        messages=[{"role": "user", "content": "Hello"}],
    )

    provider = MagicMock()
    provider.generate = AsyncMock()

    async def fake_postgres(**kwargs):
        started.set()
        await release.wait()

        request = kwargs["model_request"]

        return OrchestrationResult(
            response=ModelResponse(
                request_id=request.request_id,
                provider=request.provider,
                model=request.model,
                content="Audited response",
            ),
            session_id=str(uuid4()),
        )

    with (
        patch(
            "app.gateway.routes.postgres_runtime_enabled",
            return_value=True,
        ),
        patch(
            "app.gateway.routes.generate_postgres_response",
            side_effect=fake_postgres,
        ),
    ):
        task = asyncio.create_task(
            generate_model(
                request=model_request,
                http_request=http_request,
                http_response=Response(),
                identity=identity,
                provider_router=provider,
            )
        )

        try:
            await asyncio.wait_for(started.wait(), timeout=2)

            # Let inference and disconnect become ready together.
            release.set()
            disconnect_event.set()

            result = await asyncio.wait_for(task, timeout=2)

            assert result.content == "Audited response"

        finally:
            if not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
