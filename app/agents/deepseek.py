"""OpenAI-compatible DeepSeek benchmark agent."""

from __future__ import annotations

import os
from time import perf_counter
from typing import Any

import httpx

from app.agents.base import (
    AgentMessage,
    AgentToolCall,
    AgentToolDefinition,
    AgentTurn,
)


DEFAULT_DEEPSEEK_BASE_URL = (
    "https://api.deepseek.com"
)

DEFAULT_DEEPSEEK_MODEL = "deepseek-flash"


class DeepSeekBenchmarkAgent:
    """Use DeepSeek Flash as the agent under evaluation."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout_seconds: float = 60.0,
        input_cost_per_million: float = 0.0,
        output_cost_per_million: float = 0.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        resolved_key = (
            api_key
            or os.getenv("DEEPSEEK_API_KEY")
        )

        self._api_key = (
            resolved_key.strip()
            if resolved_key
            else ""
        )

        self._base_url = (
            base_url
            or os.getenv(
                "DEEPSEEK_BASE_URL",
                DEFAULT_DEEPSEEK_BASE_URL,
            )
        ).rstrip("/")

        self._model_name = (
            model
            or os.getenv(
                "DEEPSEEK_MODEL",
                DEFAULT_DEEPSEEK_MODEL,
            )
        )

        if timeout_seconds <= 0:
            raise ValueError(
                "timeout_seconds must be positive."
            )

        if input_cost_per_million < 0:
            raise ValueError(
                "input_cost_per_million cannot be negative."
            )

        if output_cost_per_million < 0:
            raise ValueError(
                "output_cost_per_million cannot be negative."
            )

        self._timeout_seconds = timeout_seconds
        self._input_cost_per_million = (
            input_cost_per_million
        )
        self._output_cost_per_million = (
            output_cost_per_million
        )
        self._client = client

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def configured(self) -> bool:
        return bool(self._api_key)

    def _message_payload(
        self,
        messages: list[AgentMessage],
    ) -> list[dict[str, Any]]:
        return [
            {
                "role": message.role,
                "content": message.content,
            }
            for message in messages
        ]

    def _tool_payload(
        self,
        tools: list[AgentToolDefinition],
    ) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": (
                        tool.parameters
                        or {
                            "type": "object",
                            "properties": {},
                        }
                    ),
                },
            }
            for tool in tools
        ]

    def _estimated_cost(
        self,
        *,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        input_cost = (
            input_tokens
            / 1_000_000
            * self._input_cost_per_million
        )

        output_cost = (
            output_tokens
            / 1_000_000
            * self._output_cost_per_million
        )

        return input_cost + output_cost

    async def respond(
        self,
        messages: list[AgentMessage],
        tools: list[AgentToolDefinition],
    ) -> AgentTurn:
        """Request one agent turn from DeepSeek."""

        if not self._api_key:
            raise RuntimeError(
                "DEEPSEEK_API_KEY is not configured. "
                "Set the environment variable before "
                "running the live agent benchmark."
            )

        payload: dict[str, Any] = {
            "model": self._model_name,
            "messages": self._message_payload(
                messages
            ),
            "stream": False,
        }

        if tools:
            payload["tools"] = self._tool_payload(
                tools
            )
            payload["tool_choice"] = "auto"

        headers = {
            "Authorization": (
                f"Bearer {self._api_key}"
            ),
            "Content-Type": "application/json",
        }

        owns_client = self._client is None

        client = (
            self._client
            or httpx.AsyncClient(
                timeout=self._timeout_seconds
            )
        )

        started = perf_counter()

        try:
            response = await client.post(
                (
                    f"{self._base_url}"
                    "/chat/completions"
                ),
                headers=headers,
                json=payload,
            )

            response.raise_for_status()
            body = response.json()
        finally:
            if owns_client:
                await client.aclose()

        elapsed_ms = (
            perf_counter() - started
        ) * 1000.0

        choices = body.get("choices", [])

        if not choices:
            raise RuntimeError(
                "DeepSeek returned no response choices."
            )

        message = choices[0].get(
            "message",
            {},
        )

        content = message.get("content") or ""

        tool_calls: list[AgentToolCall] = []

        for index, raw_call in enumerate(
            message.get("tool_calls") or []
        ):
            function = raw_call.get(
                "function",
                {},
            )

            arguments = function.get(
                "arguments",
                {},
            )

            if isinstance(arguments, str):
                import json

                try:
                    parsed_arguments = json.loads(
                        arguments
                    )
                except json.JSONDecodeError:
                    parsed_arguments = {
                        "_raw_arguments": arguments
                    }
            elif isinstance(arguments, dict):
                parsed_arguments = arguments
            else:
                parsed_arguments = {
                    "_raw_arguments": arguments
                }

            tool_calls.append(
                AgentToolCall(
                    call_id=(
                        raw_call.get("id")
                        or f"deepseek-call-{index}"
                    ),
                    tool_name=(
                        function.get("name")
                        or "unknown_tool"
                    ),
                    arguments=parsed_arguments,
                )
            )

        usage = body.get("usage") or {}

        input_tokens = int(
            usage.get("prompt_tokens", 0)
        )

        output_tokens = int(
            usage.get("completion_tokens", 0)
        )

        return AgentTurn(
            content=content,
            tool_calls=tool_calls,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost=self._estimated_cost(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            ),
            model_latency_ms=elapsed_ms,
            model_name=self._model_name,
        )