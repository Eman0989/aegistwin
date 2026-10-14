import asyncio

import pytest

from app.agents.base import (
    AgentToolCall,
    AgentTurn,
)
from app.contracts import (
    ModelRequest,
    TrustedIdentityContext,
)
from app.providers.commercial_adapter import (
    CommercialProviderAdapter,
)
from app.providers.errors import ProviderError


def _identity() -> TrustedIdentityContext:
    return TrustedIdentityContext(
        tenant_id="tenant-test",
        user_id="user-test",
        agent_id="agent-test",
        session_id="session-test",
        permissions={
            "model:generate"
        },
        credential_source="test",
    )


def _request(
    *,
    provider: str = "ollama",
    model: str = "llama3.2:3b",
    temperature: float = 0.7,
    stream: bool = False,
    messages: list[dict] | None = None,
) -> ModelRequest:
    return ModelRequest(
        request_id="REQ-test123",
        provider=provider,
        model=model,
        messages=(
            messages
            if messages is not None
            else [
                {
                    "role": "user",
                    "content": "Hello",
                }
            ]
        ),
        temperature=temperature,
        stream=stream,
        trusted_context=_identity(),
        metadata={},
    )


class FakeRouter:
    def __init__(
        self,
        turn: AgentTurn,
    ) -> None:
        self.turn = turn
        self.last_provider: str | None = None
        self.last_messages = None

    async def generate(
        self,
        provider: str,
        messages,
    ) -> AgentTurn:
        self.last_provider = provider
        self.last_messages = messages

        return self.turn


def test_rejects_streaming() -> None:
    adapter = CommercialProviderAdapter()

    with pytest.raises(
        ProviderError
    ) as exc_info:
        asyncio.run(
            adapter.generate(
                _request(
                    stream=True
                )
            )
        )

    assert (
        exc_info.value.code
        == "streaming_not_supported"
    )

    assert (
        exc_info.value.retryable
        is False
    )


def test_rejects_non_default_temperature() -> None:
    adapter = CommercialProviderAdapter()

    with pytest.raises(
        ProviderError
    ) as exc_info:
        asyncio.run(
            adapter.generate(
                _request(
                    temperature=0.2
                )
            )
        )

    assert (
        exc_info.value.code
        == "unsupported_temperature"
    )

    assert (
        exc_info.value.retryable
        is False
    )


def test_converts_request_and_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = CommercialProviderAdapter()

    fake_router = FakeRouter(
        AgentTurn(
            content="Hello from Ollama.",
            input_tokens=10,
            output_tokens=5,
            estimated_cost=0.01,
            model_latency_ms=25.5,
            model_name="llama3.2:3b",
        )
    )

    monkeypatch.setattr(
        adapter,
        "_build_router",
        lambda **_: fake_router,
    )

    response = asyncio.run(
        adapter.generate(
            _request()
        )
    )

    assert (
        fake_router.last_provider
        == "ollama"
    )

    assert (
        fake_router.last_messages
        is not None
    )

    assert len(
        fake_router.last_messages
    ) == 1

    message = (
        fake_router.last_messages[0]
    )

    assert message.role == "user"
    assert message.content == "Hello"

    assert (
        response.request_id
        == "REQ-test123"
    )

    assert (
        response.provider
        == "ollama"
    )

    assert (
        response.model
        == "llama3.2:3b"
    )

    assert (
        response.content
        == "Hello from Ollama."
    )

    assert (
        response.usage[
            "input_tokens"
        ]
        == 10
    )

    assert (
        response.usage[
            "output_tokens"
        ]
        == 5
    )

    assert (
        response.usage[
            "estimated_cost"
        ]
        == 0.01
    )

    assert (
        response.latency_ms
        == 25.5
    )

    assert (
        response.finish_reason
        == "stop"
    )


def test_preserves_tool_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = CommercialProviderAdapter()

    fake_router = FakeRouter(
        AgentTurn(
            content="",
            tool_calls=[
                AgentToolCall(
                    call_id="call-123",
                    tool_name=(
                        "customer_database"
                    ),
                    arguments={
                        "customer_id": "42"
                    },
                )
            ],
            model_name="llama3.2:3b",
        )
    )

    monkeypatch.setattr(
        adapter,
        "_build_router",
        lambda **_: fake_router,
    )

    response = asyncio.run(
        adapter.generate(
            _request()
        )
    )

    assert (
        response.finish_reason
        == "tool_calls"
    )

    assert len(
        response.tool_calls
    ) == 1

    assert (
        response.tool_calls[0][
            "call_id"
        ]
        == "call-123"
    )

    assert (
        response.tool_calls[0][
            "tool_name"
        ]
        == "customer_database"
    )

    assert (
        response.tool_calls[0][
            "arguments"
        ]
        == {
            "customer_id": "42"
        }
    )


def test_rejects_invalid_message_role() -> None:
    adapter = CommercialProviderAdapter()

    with pytest.raises(
        ProviderError
    ) as exc_info:
        asyncio.run(
            adapter.generate(
                _request(
                    messages=[
                        {
                            "role": "",
                            "content": "Hello",
                        }
                    ]
                )
            )
        )

    assert (
        exc_info.value.code
        == "invalid_request"
    )


def test_rejects_unsupported_provider() -> None:
    adapter = CommercialProviderAdapter()

    with pytest.raises(
        ProviderError
    ) as exc_info:
        asyncio.run(
            adapter.generate(
                _request(
                    provider="unknown-provider"
                )
            )
        )

    assert (
        exc_info.value.code
        == "unsupported_provider"
    )

    assert (
        exc_info.value.retryable
        is False
    )