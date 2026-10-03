"""Model-independent contracts for benchmark agents."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class AgentMessage:
    """One message in an agent conversation."""

    role: str
    content: str
    metadata: dict[str, Any] = field(
        default_factory=dict
    )


@dataclass(frozen=True)
class AgentToolDefinition:
    """A tool the benchmark agent may request."""

    name: str
    description: str
    parameters: dict[str, Any] = field(
        default_factory=dict
    )


@dataclass(frozen=True)
class AgentToolCall:
    """A tool call proposed by an agent model."""

    call_id: str
    tool_name: str
    arguments: dict[str, Any] = field(
        default_factory=dict
    )


@dataclass(frozen=True)
class AgentTurn:
    """The agent model's response for one turn."""

    content: str = ""
    tool_calls: list[AgentToolCall] = field(
        default_factory=list
    )
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost: float = 0.0
    model_latency_ms: float = 0.0
    model_name: str = "unknown"

    @property
    def requested_tool_execution(self) -> bool:
        return bool(self.tool_calls)


class BenchmarkAgent(Protocol):
    """Interface implemented by every benchmark agent."""

    @property
    def model_name(self) -> str:
        """Return the model identifier."""

    async def respond(
        self,
        messages: list[AgentMessage],
        tools: list[AgentToolDefinition],
    ) -> AgentTurn:
        """Generate the next response or proposed tool call."""


class ScriptedBenchmarkAgent:
    """Predictable test agent that requires no external API."""

    def __init__(
        self,
        turns: list[AgentTurn],
        *,
        model_name: str = "scripted-test-agent",
    ) -> None:
        self._turns = list(turns)
        self._model_name = model_name
        self._position = 0

    @property
    def model_name(self) -> str:
        return self._model_name

    async def respond(
        self,
        messages: list[AgentMessage],
        tools: list[AgentToolDefinition],
    ) -> AgentTurn:
        del messages
        del tools

        if self._position >= len(self._turns):
            return AgentTurn(
                content="Task completed.",
                model_name=self._model_name,
            )

        turn = self._turns[self._position]
        self._position += 1

        if turn.model_name == "unknown":
            return AgentTurn(
                content=turn.content,
                tool_calls=turn.tool_calls,
                input_tokens=turn.input_tokens,
                output_tokens=turn.output_tokens,
                estimated_cost=turn.estimated_cost,
                model_latency_ms=(
                    turn.model_latency_ms
                ),
                model_name=self._model_name,
            )

        return turn