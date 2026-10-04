"""Local Ollama benchmark agent."""

from __future__ import annotations

import os
from time import perf_counter
from typing import Any
from uuid import uuid4

import httpx

from app.agents.base import (
    AgentMessage,
    AgentToolCall,
    AgentToolDefinition,
    AgentTurn,
)


DEFAULT_OLLAMA_BASE_URL = (
    "http://127.0.0.1:11434"
)

DEFAULT_OLLAMA_MODEL = "llama3.2:3b"


class OllamaBenchmarkAgent:
    """Use a local Ollama model as the agent under evaluation."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        model: str | None = None,
        timeout_seconds: float = 180.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = (
            base_url
            or os.getenv(
                "OLLAMA_BASE_URL",
                DEFAULT_OLLAMA_BASE_URL,
            )
        ).rstrip("/")

        self._model_name = (
            model
            or os.getenv(
                "OLLAMA_MODEL",
                DEFAULT_OLLAMA_MODEL,
            )
        )

        if timeout_seconds <= 0:
            raise ValueError(
                "timeout_seconds must be positive."
            )

        self._timeout_seconds = timeout_seconds
        self._client = client

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def base_url(self) -> str:
        return self._base_url

    def _message_payload(
        self,
        messages: list[AgentMessage],
    ) -> list[dict[str, Any]]:
        payload: list[dict[str, Any]] = []

        for message in messages:
            item: dict[str, Any] = {
                "role": message.role,
                "content": message.content,
            }

            if message.role == "assistant":
                tool_calls = message.metadata.get(
                    "tool_calls"
                )

                if tool_calls:
                    item["tool_calls"] = tool_calls

            if message.role == "tool":
                tool_name = (
                    message.metadata.get("tool_name")
                    or message.metadata.get("name")
                )

                if tool_name:
                    item["tool_name"] = str(
                        tool_name
                    )

            payload.append(item)

        return payload

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

    async def respond(
        self,
        messages: list[AgentMessage],
        tools: list[AgentToolDefinition],
    ) -> AgentTurn:
        """Request one turn from the local Ollama server."""

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
                f"{self._base_url}/api/chat",
                json=payload,
            )

            response.raise_for_status()
            body = response.json()

        except httpx.ConnectError as error:
            raise RuntimeError(
                "Cannot connect to Ollama at "
                f"{self._base_url}. Open the Ollama "
                "application or run `ollama serve`."
            ) from error

        except httpx.TimeoutException as error:
            raise RuntimeError(
                "The Ollama request timed out while "
                f"running {self._model_name}."
            ) from error

        except httpx.HTTPStatusError as error:
            detail = error.response.text[:500]

            raise RuntimeError(
                "Ollama returned HTTP "
                f"{error.response.status_code}: "
                f"{detail}"
            ) from error

        finally:
            if owns_client:
                await client.aclose()

        elapsed_ms = (
            perf_counter() - started
        ) * 1000.0

        message = body.get("message")

        if not isinstance(message, dict):
            raise RuntimeError(
                "Ollama returned no assistant message."
            )

        content = str(
            message.get("content") or ""
        )

        tool_calls: list[AgentToolCall] = []

        raw_tool_calls = (
            message.get("tool_calls")
            or []
        )

        for index, raw_call in enumerate(
            raw_tool_calls
        ):
            if not isinstance(raw_call, dict):
                continue

            function = (
                raw_call.get("function")
                or {}
            )

            if not isinstance(function, dict):
                function = {}

            arguments = (
                function.get("arguments")
                or {}
            )

            if not isinstance(arguments, dict):
                arguments = {
                    "_raw_arguments": arguments
                }

            call_id = (
                raw_call.get("id")
                or (
                    "ollama-call-"
                    f"{uuid4().hex[:8]}-{index}"
                )
            )

            tool_calls.append(
                AgentToolCall(
                    call_id=str(call_id),
                    tool_name=str(
                        function.get("name")
                        or "unknown_tool"
                    ),
                    arguments=arguments,
                )
            )

        input_tokens = int(
            body.get(
                "prompt_eval_count",
                0,
            )
            or 0
        )

        output_tokens = int(
            body.get(
                "eval_count",
                0,
            )
            or 0
        )

        return AgentTurn(
            content=content,
            tool_calls=tool_calls,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost=0.0,
            model_latency_ms=elapsed_ms,
            model_name=self._model_name,
        )