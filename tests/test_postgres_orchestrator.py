
"""Tests for PostgreSQL-backed inference orchestration."""

import asyncio
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.contracts import (
    ModelRequest,
    ModelResponse,
    TrustedIdentityContext,
)
from app.gateway.postgres_orchestrator import (
    RequestLeaseError,
    ResponseBlockedError,
    run_postgres_inference,
)
from app.gateway.postgres_request_lifecycle import PersistedRequest
from app.gateway.postgres_session_manager import ManagedSession
from app.gateway.postgres_session_resolver import SessionAccessDenied
from app.security.llm_response_inspector import (
    ResponseAction,
    ResponseInspection,
)
from app.providers.errors import ProviderError


def make_request():
    return ModelRequest(
        request_id="REQ-test123",
        provider="ollama",
        model="llama3.2:3b",
        messages=[{"role": "user", "content": "Hello"}],
        trusted_context=TrustedIdentityContext(
            tenant_id=str(uuid4()),
            agent_id=str(uuid4()),
            user_id="test-user",
            session_id="SES-legacy",
        ),
    )


def make_response(request):
    return ModelResponse(
        request_id=request.request_id,
        provider=request.provider,
        model=request.model,
        content="Safe model response.",
        usage={"input_tokens": 5, "output_tokens": 7},
        latency_ms=10.5,
    )


@pytest.fixture
def setup_orchestrator():
    db = MagicMock()
    request = make_request()
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

    manager = patch(
        "app.gateway.postgres_orchestrator.manage_postgres_session",
        return_value=managed,
    )

    starter = patch(
        "app.gateway.postgres_orchestrator.start_leased_request",
        return_value=persisted,
    )

    finisher = patch(
        "app.gateway.postgres_orchestrator.finish_request",
        return_value=persisted.request_id,
    )

    renewer = patch(
        "app.gateway.postgres_orchestrator.renew_request_lease",
        return_value=True,
    )

    with (
        manager as mock_manager,
        starter as mock_start,
        finisher as mock_finish,
        renewer as mock_renew,
    ):
        yield {
            "db": db,
            "request": request,
            "managed": managed,
            "persisted": persisted,
            "manager": mock_manager,
            "start": mock_start,
            "finish": mock_finish,
            "renew": mock_renew,
        }


@pytest.mark.asyncio
async def test_safe_response(setup_orchestrator):
    ctx = setup_orchestrator
    provider = MagicMock()
    provider.generate = AsyncMock(
        return_value=make_response(ctx["request"])
    )

    with patch(
        "app.gateway.postgres_orchestrator.inspect_response",
        return_value=ResponseInspection(
            action=ResponseAction.ALLOW,
            content="Safe model response.",
            reason="Safe.",
        ),
    ):
        result = await run_postgres_inference(
            model_request=ctx["request"],
            provider_router=provider,
            db=ctx["db"],
            requested_session_id=None,
        )

    assert result.response.content == "Safe model response."
    assert result.session_id == str(ctx["managed"].session_id)
    ctx["db"].commit.assert_called_once()
    ctx["finish"].assert_called_once()
    assert ctx["finish"].call_args.kwargs["outcome"] == "completed"

    ctx["start"].assert_called_once()
    assert ctx["start"].call_args.kwargs["lease_seconds"] == 60
    assert ctx["start"].call_args.kwargs["worker_id"].startswith(
        "aegis-worker-"
    )

    assert (
        ctx["finish"].call_args.kwargs["request"].lease_token
        == "test-lease-token"
    )


@pytest.mark.asyncio
async def test_redacted_response(setup_orchestrator):
    ctx = setup_orchestrator
    provider = MagicMock()
    provider.generate = AsyncMock(
        return_value=make_response(ctx["request"]).model_copy(
            update={"content": "Contact alice@example.com."}
        )
    )

    with patch(
        "app.gateway.postgres_orchestrator.inspect_response",
        return_value=ResponseInspection(
            action=ResponseAction.REDACT,
            content="Contact [REDACTED].",
            reason="Redacted.",
        ),
    ):
        result = await run_postgres_inference(
            model_request=ctx["request"],
            provider_router=provider,
            db=ctx["db"],
            requested_session_id=None,
        )

    assert result.response.content == "Contact [REDACTED]."
    assert ctx["finish"].call_args.kwargs["outcome"] == "completed"


@pytest.mark.asyncio
async def test_blocked_response(setup_orchestrator):
    ctx = setup_orchestrator
    provider = MagicMock()
    provider.generate = AsyncMock(
        return_value=make_response(ctx["request"])
    )

    with patch(
        "app.gateway.postgres_orchestrator.inspect_response",
        return_value=ResponseInspection(
            action=ResponseAction.BLOCK,
            content=None,
            reason="Blocked.",
        ),
    ):
        with pytest.raises(ResponseBlockedError):
            await run_postgres_inference(
                model_request=ctx["request"],
                provider_router=provider,
                db=ctx["db"],
                requested_session_id=None,
            )

    assert ctx["finish"].call_args.kwargs["outcome"] == "blocked"


@pytest.mark.asyncio
async def test_provider_failure(setup_orchestrator):
    ctx = setup_orchestrator
    provider = MagicMock()
    provider.generate = AsyncMock(
        side_effect=ProviderError(
            "Simulated outage",
            code="provider_unavailable",
            retryable=True,
        )
    )

    with pytest.raises(ProviderError):
        await run_postgres_inference(
            model_request=ctx["request"],
            provider_router=provider,
            db=ctx["db"],
            requested_session_id=None,
        )

    assert ctx["finish"].call_args.kwargs["outcome"] == "failed"
    assert (
        ctx["finish"].call_args.kwargs["error_code"]
        == "provider_unavailable"
    )


@pytest.mark.asyncio
async def test_unauthorized_session_blocks_inference(setup_orchestrator):
    ctx = setup_orchestrator
    ctx["manager"].side_effect = SessionAccessDenied(
        "Session is not authorized."
    )

    provider = MagicMock()
    provider.generate = AsyncMock()

    with pytest.raises(SessionAccessDenied):
        await run_postgres_inference(
            model_request=ctx["request"],
            provider_router=provider,
            db=ctx["db"],
            requested_session_id=str(uuid4()),
        )

    provider.generate.assert_not_awaited()
    ctx["start"].assert_not_called()
    ctx["db"].commit.assert_not_called()


@pytest.mark.asyncio
async def test_database_commit_failure_blocks_inference(setup_orchestrator):
    ctx = setup_orchestrator
    ctx["db"].commit.side_effect = RuntimeError(
        "Database unavailable"
    )

    provider = MagicMock()
    provider.generate = AsyncMock()

    with pytest.raises(RuntimeError, match="Database unavailable"):
        await run_postgres_inference(
            model_request=ctx["request"],
            provider_router=provider,
            db=ctx["db"],
            requested_session_id=None,
        )

    provider.generate.assert_not_awaited()
    ctx["start"].assert_called_once()
    ctx["db"].rollback.assert_called_once()
    ctx["finish"].assert_not_called()


@pytest.mark.asyncio
async def test_mismatched_provider_request_id_is_blocked(
    setup_orchestrator,
):
    ctx = setup_orchestrator

    response = make_response(ctx["request"]).model_copy(
        update={"request_id": "REQ-different"}
    )

    provider = MagicMock()
    provider.generate = AsyncMock(return_value=response)

    with pytest.raises(ResponseBlockedError):
        await run_postgres_inference(
            model_request=ctx["request"],
            provider_router=provider,
            db=ctx["db"],
            requested_session_id=None,
        )

    assert ctx["finish"].call_args.kwargs["outcome"] == "blocked"


@pytest.mark.asyncio
async def test_inconsistent_allow_result_is_blocked(
    setup_orchestrator,
):
    ctx = setup_orchestrator

    provider = MagicMock()
    provider.generate = AsyncMock(
        return_value=make_response(ctx["request"])
    )

    with patch(
        "app.gateway.postgres_orchestrator.inspect_response",
        return_value=ResponseInspection(
            action=ResponseAction.ALLOW,
            content="Unexpected replacement content.",
            reason="Inconsistent inspection.",
        ),
    ):
        with pytest.raises(ResponseBlockedError):
            await run_postgres_inference(
                model_request=ctx["request"],
                provider_router=provider,
                db=ctx["db"],
                requested_session_id=None,
            )

    assert ctx["finish"].call_args.kwargs["outcome"] == "blocked"


@pytest.mark.asyncio
async def test_inspector_exception_blocks_response(setup_orchestrator):
    ctx = setup_orchestrator
    provider = MagicMock()
    provider.generate = AsyncMock(
        return_value=make_response(ctx["request"])
    )

    with patch(
        "app.gateway.postgres_orchestrator.inspect_response",
        side_effect=RuntimeError("Inspector unavailable"),
    ):
        with pytest.raises(ResponseBlockedError):
            await run_postgres_inference(
                model_request=ctx["request"],
                provider_router=provider,
                db=ctx["db"],
                requested_session_id=None,
            )

    assert ctx["finish"].call_args.kwargs["outcome"] == "blocked"


@pytest.mark.asyncio
async def test_audit_completion_failure_prevents_response(
    setup_orchestrator,
):
    ctx = setup_orchestrator
    ctx["finish"].side_effect = RuntimeError("Database unavailable")

    provider = MagicMock()
    provider.generate = AsyncMock(
        return_value=make_response(ctx["request"])
    )

    with pytest.raises(RuntimeError, match="Database unavailable"):
        await run_postgres_inference(
            model_request=ctx["request"],
            provider_router=provider,
            db=ctx["db"],
            requested_session_id=None,
        )

    ctx["finish"].assert_called_once()


@pytest.mark.asyncio
async def test_invalid_usage_metrics_prevent_success(setup_orchestrator):
    ctx = setup_orchestrator
    provider = MagicMock()
    provider.generate = AsyncMock(
        return_value=make_response(ctx["request"]).model_copy(
            update={"usage": {"input_tokens": -5, "output_tokens": 7}}
        )
    )

    with pytest.raises(ResponseBlockedError):
        await run_postgres_inference(
            model_request=ctx["request"],
            provider_router=provider,
            db=ctx["db"],
            requested_session_id=None,
        )

    assert ctx["finish"].call_args.kwargs["outcome"] == "blocked"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "field,incorrect_value",
    [
        ("provider", "unexpected-provider"),
        ("model", "unexpected-model"),
    ],
)
async def test_mismatched_provider_metadata_is_blocked(
    setup_orchestrator,
    field,
    incorrect_value,
):
    ctx = setup_orchestrator

    response = make_response(ctx["request"]).model_copy(
        update={field: incorrect_value}
    )

    provider = MagicMock()
    provider.generate = AsyncMock(return_value=response)

    with pytest.raises(ResponseBlockedError):
        await run_postgres_inference(
            model_request=ctx["request"],
            provider_router=provider,
            db=ctx["db"],
            requested_session_id=None,
        )

    assert ctx["finish"].call_args.kwargs["outcome"] == "blocked"


@pytest.mark.asyncio
async def test_invalid_redacted_content_is_blocked(
    setup_orchestrator,
):
    ctx = setup_orchestrator

    provider = MagicMock()
    provider.generate = AsyncMock(
        return_value=make_response(ctx["request"])
    )

    with patch(
        "app.gateway.postgres_orchestrator.inspect_response",
        return_value=ResponseInspection(
            action=ResponseAction.REDACT,
            content=None,
            reason="Invalid redaction.",
        ),
    ):
        with pytest.raises(ResponseBlockedError):
            await run_postgres_inference(
                model_request=ctx["request"],
                provider_router=provider,
                db=ctx["db"],
                requested_session_id=None,
            )

    assert ctx["finish"].call_args.kwargs["outcome"] == "blocked"


@pytest.mark.asyncio
async def test_unknown_inspection_action_is_blocked(
    setup_orchestrator,
):
    ctx = setup_orchestrator

    provider = MagicMock()
    provider.generate = AsyncMock(
        return_value=make_response(ctx["request"])
    )

    with patch(
        "app.gateway.postgres_orchestrator.inspect_response",
        return_value=ResponseInspection(
            action="UNKNOWN",
            content="Safe model response.",
            reason="Invalid action.",
        ),
    ):
        with pytest.raises(ResponseBlockedError):
            await run_postgres_inference(
                model_request=ctx["request"],
                provider_router=provider,
                db=ctx["db"],
                requested_session_id=None,
            )

    assert ctx["finish"].call_args.kwargs["outcome"] == "blocked"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "invalid_value",
    [True, -1, 1.5, "7"],
)
async def test_invalid_token_types_are_blocked(
    setup_orchestrator,
    invalid_value,
):
    ctx = setup_orchestrator

    response = make_response(ctx["request"]).model_copy(
        update={
            "usage": {
                "input_tokens": invalid_value,
                "output_tokens": 7,
            }
        }
    )

    provider = MagicMock()
    provider.generate = AsyncMock(return_value=response)

    with pytest.raises(ResponseBlockedError):
        await run_postgres_inference(
            model_request=ctx["request"],
            provider_router=provider,
            db=ctx["db"],
            requested_session_id=None,
        )

    assert ctx["finish"].call_args.kwargs["outcome"] == "blocked"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "invalid_latency",
    [float("nan"), float("inf"), float("-inf"), -1.0, True],
)
async def test_invalid_latency_is_blocked(
    setup_orchestrator,
    invalid_latency,
):
    ctx = setup_orchestrator

    response = make_response(ctx["request"]).model_copy(
        update={"latency_ms": invalid_latency}
    )

    provider = MagicMock()
    provider.generate = AsyncMock(return_value=response)

    with pytest.raises(ResponseBlockedError):
        await run_postgres_inference(
            model_request=ctx["request"],
            provider_router=provider,
            db=ctx["db"],
            requested_session_id=None,
        )

    assert ctx["finish"].call_args.kwargs["outcome"] == "blocked"


@pytest.mark.asyncio
async def test_lease_loss_prevents_model_response_release(
    setup_orchestrator,
):
    """A worker that loses its lease cannot release LLM output."""

    ctx = setup_orchestrator

    provider = MagicMock()
    provider.generate = AsyncMock(
        return_value=make_response(ctx["request"])
    )

    @asynccontextmanager
    async def lost_heartbeat(persisted, worker_id):
        lost = asyncio.Event()
        lost.set()
        yield lost

    with patch(
        "app.gateway.postgres_orchestrator._lease_heartbeat",
        lost_heartbeat,
    ):
        with pytest.raises(RequestLeaseError):
            await run_postgres_inference(
                model_request=ctx["request"],
                provider_router=provider,
                db=ctx["db"],
                requested_session_id=None,
            )

    provider.generate.assert_awaited_once()
    ctx["finish"].assert_not_called()
