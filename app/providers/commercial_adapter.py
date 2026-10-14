"""Bridge commercial gateway contracts to real LLM providers."""

from __future__ import annotations

from app.agents.base import (
    AgentMessage,
    AgentToolCall,
    AgentTurn,
)
from app.contracts import (
    ModelRequest,
    ModelResponse,
)
from app.providers.errors import (
    ProviderError as RuntimeProviderError,
)
from app.providers.ollama import OllamaProvider
from app.providers.openai_compatible import (
    OpenAICompatibleProvider,
)
from app.providers.router import ProviderRouter


class CommercialProviderAdapter:
    """Adapt commercial gateway requests to the provider layer."""

    async def generate(
        self,
        request: ModelRequest,
    ) -> ModelResponse:
        """Generate one normalized commercial model response."""

        if request.stream:
            raise RuntimeProviderError(
                (
                    "Streaming is not enabled on the "
                    "commercial gateway yet."
                ),
                code="streaming_not_supported",
                retryable=False,
            )

        if request.temperature != 0.7:
            raise RuntimeProviderError(
                (
                    "Per-request temperature is not "
                    "supported yet. Use the default "
                    "temperature of 0.7."
                ),
                code="unsupported_temperature",
                retryable=False,
            )

        messages = self._convert_messages(
            request
        )

        provider_name = (
            request.provider
            .strip()
            .lower()
        )

        router = self._build_router(
            provider_name=provider_name,
            model=request.model,
        )

        turn = await router.generate(
            provider_name,
            messages,
        )

        return self._convert_response(
            request=request,
            turn=turn,
        )

    def _build_router(
        self,
        *,
        provider_name: str,
        model: str,
    ) -> ProviderRouter:
        """Build a router for the requested provider and model."""

        if provider_name == "ollama":
            provider = OllamaProvider(
                model=model
            )

        elif provider_name in {
            "openai",
            "openai_compatible",
            "openai-compatible",
        }:
            provider = OpenAICompatibleProvider(
                model=model
            )

        else:
            raise RuntimeProviderError(
                (
                    "Unsupported model provider: "
                    f"{provider_name}"
                ),
                code="unsupported_provider",
                retryable=False,
            )

        return ProviderRouter(
            providers={
                provider_name: provider
            }
        )

    def _convert_messages(
        self,
        request: ModelRequest,
    ) -> list[AgentMessage]:
        """Convert gateway messages to provider messages."""

        converted: list[AgentMessage] = []

        for index, item in enumerate(
            request.messages
        ):
            role = item.get("role")
            content = item.get("content")

            if (
                not isinstance(role, str)
                or not role.strip()
            ):
                raise RuntimeProviderError(
                    (
                        "Invalid role in message "
                        f"{index}."
                    ),
                    code="invalid_request",
                    retryable=False,
                )

            if not isinstance(
                content,
                str,
            ):
                raise RuntimeProviderError(
                    (
                        "Invalid content in message "
                        f"{index}."
                    ),
                    code="invalid_request",
                    retryable=False,
                )

            metadata = item.get(
                "metadata",
                {},
            )

            if not isinstance(
                metadata,
                dict,
            ):
                raise RuntimeProviderError(
                    (
                        "Invalid metadata in message "
                        f"{index}."
                    ),
                    code="invalid_request",
                    retryable=False,
                )

            converted.append(
                AgentMessage(
                    role=role.strip(),
                    content=content,
                    metadata=metadata,
                )
            )

        return converted

    def _convert_response(
        self,
        *,
        request: ModelRequest,
        turn: AgentTurn,
    ) -> ModelResponse:
        """Convert AgentTurn to ModelResponse."""

        tool_calls = [
            self._convert_tool_call(
                call
            )
            for call in turn.tool_calls
        ]

        model_name = (
            turn.model_name
            if (
                turn.model_name
                and turn.model_name
                != "unknown"
            )
            else request.model
        )

        finish_reason = (
            "tool_calls"
            if tool_calls
            else "stop"
        )

        return ModelResponse(
            request_id=request.request_id,
            provider=request.provider,
            model=model_name,
            content=turn.content,
            tool_calls=tool_calls,
            usage={
                "input_tokens": (
                    turn.input_tokens
                ),
                "output_tokens": (
                    turn.output_tokens
                ),
                "estimated_cost": (
                    turn.estimated_cost
                ),
            },
            finish_reason=finish_reason,
            latency_ms=(
                turn.model_latency_ms
            ),
        )

    @staticmethod
    def _convert_tool_call(
        call: AgentToolCall,
    ) -> dict[str, object]:
        """Convert one provider tool call."""

        return {
            "call_id": call.call_id,
            "tool_name": call.tool_name,
            "arguments": call.arguments,
        }