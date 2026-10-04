from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.controls.budget import (
    BudgetManager,
)
from app.controls.policy import (
    PolicyEngine,
)
from app.gateway.service import Gateway
from app.security.agent_benchmark import (
    BenchmarkScenario,
)
from app.security.agent_runner import (
    run_agent_scenario,
)


class FakeAgent:
    def __init__(
        self,
        turns: list[Any],
    ) -> None:
        self._turns = list(
            turns
        )

        self._index = 0

    @property
    def model_name(
        self,
    ) -> str:
        return "resource-test-model"

    async def respond(
        self,
        messages: Any,
        tools: Any,
    ) -> Any:
        if (
            self._index
            >= len(
                self._turns
            )
        ):
            return make_turn(
                content="Done."
            )

        turn = (
            self._turns[
                self._index
            ]
        )

        self._index += 1

        return turn


def make_tool_call(
    *,
    call_id: str = "CALL-TEST",
    tool_name: str = "summarizer",
    arguments: dict[
        str,
        Any,
    ] | None = None,
) -> Any:
    return SimpleNamespace(
        call_id=call_id,
        tool_name=tool_name,
        arguments=(
            arguments
            or {
                "content": (
                    "Summarize this text."
                )
            }
        ),
    )


def make_turn(
    *,
    content: str = "",
    tool_calls: list[
        Any
    ] | None = None,
    input_tokens: int = 10,
    output_tokens: int = 5,
    model_latency_ms: float = 10.0,
    estimated_cost: float = 0.0,
) -> Any:
    return SimpleNamespace(
        content=content,
        tool_calls=(
            list(
                tool_calls
                or []
            )
        ),
        input_tokens=(
            input_tokens
        ),
        output_tokens=(
            output_tokens
        ),
        model_latency_ms=(
            model_latency_ms
        ),
        estimated_cost=(
            estimated_cost
        ),
        model_name=(
            "resource-test-model"
        ),
    )


def make_scenario(
    scenario_id: str,
    *,
    max_agent_turns: int = 6,
) -> BenchmarkScenario:
    return BenchmarkScenario(
        scenario_id=scenario_id,
        name=(
            "Resource governance test"
        ),
        category=(
            "resource_governance"
        ),
        kind="legitimate",
        user_task=(
            "Summarize the supplied text."
        ),
        instruction_origin="USER",
        available_tools=[
            "summarizer"
        ],
        expected_outcome="ALLOW",
        requires_model=False,
        max_agent_turns=(
            max_agent_turns
        ),
    )


def make_gateway(
    budget_manager: BudgetManager,
) -> Gateway:
    return Gateway(
        PolicyEngine(),
        budget_manager=(
            budget_manager
        ),
        enforce_tool_allow_list=True,
        enforce_semantic=False,
        enforce_composition=False,
        enforce_deterministic_policy=False,
        enforce_human_approval=False,
        enforce_budget=True,
    )


@pytest.mark.asyncio
async def test_agent_turn_limit_blocks_before_tool_execution() -> None:
    budget = BudgetManager(
        max_agent_turns=0,
    )

    gateway = make_gateway(
        budget
    )

    agent = FakeAgent(
        [
            make_turn(
                tool_calls=[
                    make_tool_call()
                ]
            )
        ]
    )

    result = (
        await run_agent_scenario(
            make_scenario(
                "TURN-LIMIT"
            ),
            agent,
            gateway_factory=(
                lambda: gateway
            ),
        )
    )

    assert (
        result.actual_outcome
        == "BLOCK"
    )

    assert (
        "agent turns"
        in result.reason.lower()
    )

    assert (
        result.executed_tool_calls
        == 0
    )


@pytest.mark.asyncio
async def test_input_token_limit_blocks_before_tool_execution() -> None:
    budget = BudgetManager(
        max_input_tokens=5,
    )

    gateway = make_gateway(
        budget
    )

    agent = FakeAgent(
        [
            make_turn(
                input_tokens=10,
                tool_calls=[
                    make_tool_call()
                ],
            )
        ]
    )

    result = (
        await run_agent_scenario(
            make_scenario(
                "INPUT-LIMIT"
            ),
            agent,
            gateway_factory=(
                lambda: gateway
            ),
        )
    )

    assert (
        result.actual_outcome
        == "BLOCK"
    )

    assert (
        "input-token"
        in result.reason.lower()
    )

    assert (
        result.executed_tool_calls
        == 0
    )


@pytest.mark.asyncio
async def test_output_token_limit_blocks_before_tool_execution() -> None:
    budget = BudgetManager(
        max_output_tokens=2,
    )

    gateway = make_gateway(
        budget
    )

    agent = FakeAgent(
        [
            make_turn(
                output_tokens=5,
                tool_calls=[
                    make_tool_call()
                ],
            )
        ]
    )

    result = (
        await run_agent_scenario(
            make_scenario(
                "OUTPUT-LIMIT"
            ),
            agent,
            gateway_factory=(
                lambda: gateway
            ),
        )
    )

    assert (
        result.actual_outcome
        == "BLOCK"
    )

    assert (
        "output-token"
        in result.reason.lower()
    )

    assert (
        result.executed_tool_calls
        == 0
    )


@pytest.mark.asyncio
async def test_model_runtime_limit_blocks_before_tool_execution() -> None:
    budget = BudgetManager(
        max_model_runtime_ms=5.0,
    )

    gateway = make_gateway(
        budget
    )

    agent = FakeAgent(
        [
            make_turn(
                model_latency_ms=10.0,
                tool_calls=[
                    make_tool_call()
                ],
            )
        ]
    )

    result = (
        await run_agent_scenario(
            make_scenario(
                "MODEL-RUNTIME-LIMIT"
            ),
            agent,
            gateway_factory=(
                lambda: gateway
            ),
        )
    )

    assert (
        result.actual_outcome
        == "BLOCK"
    )

    assert (
        "model runtime"
        in result.reason.lower()
    )

    assert (
        result.executed_tool_calls
        == 0
    )


@pytest.mark.asyncio
async def test_execution_duration_limit_blocks() -> None:
    budget = BudgetManager(
        max_execution_duration_ms=0.0,
    )

    gateway = make_gateway(
        budget
    )

    agent = FakeAgent(
        [
            make_turn(
                tool_calls=[
                    make_tool_call()
                ],
            )
        ]
    )

    result = (
        await run_agent_scenario(
            make_scenario(
                "EXECUTION-LIMIT"
            ),
            agent,
            gateway_factory=(
                lambda: gateway
            ),
        )
    )

    assert (
        result.actual_outcome
        == "BLOCK"
    )

    assert (
        "execution duration"
        in result.reason.lower()
    )

    assert (
        result.executed_tool_calls
        == 0
    )


@pytest.mark.asyncio
async def test_resource_usage_accumulates_across_agent_turns() -> None:
    budget = BudgetManager(
        max_agent_turns=5,
        max_input_tokens=1000,
        max_output_tokens=1000,
        max_model_runtime_ms=1000.0,
        max_execution_duration_ms=1000.0,
    )

    gateway = make_gateway(
        budget
    )

    agent = FakeAgent(
        [
            make_turn(
                input_tokens=10,
                output_tokens=4,
                model_latency_ms=7.0,
                tool_calls=[
                    make_tool_call(
                        call_id="CALL-FIRST"
                    )
                ],
            ),
            make_turn(
                content="Summary complete.",
                input_tokens=20,
                output_tokens=6,
                model_latency_ms=8.0,
            ),
        ]
    )

    result = (
        await run_agent_scenario(
            make_scenario(
                "ACCUMULATION"
            ),
            agent,
            gateway_factory=(
                lambda: gateway
            ),
        )
    )

    assert (
        result.actual_outcome
        == "ALLOW"
    )

    assert (
        result.input_tokens
        == 30
    )

    assert (
        result.output_tokens
        == 10
    )

    assert (
        result.model_latency_ms
        == 15.0
    )

    snapshots = (
        budget.snapshots()
    )

    assert (
        len(snapshots)
        == 1
    )

    usage = next(
        iter(
            snapshots.values()
        )
    )

    assert (
        usage.agent_turns
        == 2
    )

    assert (
        usage.input_tokens
        == 30
    )

    assert (
        usage.output_tokens
        == 10
    )

    assert (
        usage.model_runtime_ms
        == 15.0
    )

    assert (
        usage.tool_calls
        == 1
    )


@pytest.mark.asyncio
async def test_normal_agent_workflow_remains_allowed() -> None:
    budget = BudgetManager(
        max_tool_calls=10,
        max_agent_turns=10,
        max_input_tokens=10_000,
        max_output_tokens=10_000,
        max_model_runtime_ms=10_000.0,
        max_execution_duration_ms=10_000.0,
    )

    gateway = make_gateway(
        budget
    )

    agent = FakeAgent(
        [
            make_turn(
                input_tokens=50,
                output_tokens=10,
                model_latency_ms=5.0,
                tool_calls=[
                    make_tool_call(
                        call_id="CALL-NORMAL"
                    )
                ],
            ),
            make_turn(
                content=(
                    "The summary is complete."
                ),
                input_tokens=40,
                output_tokens=12,
                model_latency_ms=5.0,
            ),
        ]
    )

    result = (
        await run_agent_scenario(
            make_scenario(
                "NORMAL-WORKFLOW"
            ),
            agent,
            gateway_factory=(
                lambda: gateway
            ),
        )
    )

    assert (
        result.actual_outcome
        == "ALLOW"
    )

    assert (
        result.executed_tool_calls
        == 1
    )

    assert (
        result.input_tokens
        == 90
    )

    assert (
        result.output_tokens
        == 22
    )


@pytest.mark.asyncio
async def test_resource_limits_are_bypassed_when_budget_control_disabled() -> None:
    budget = BudgetManager(
        max_agent_turns=0,
        max_input_tokens=0,
        max_output_tokens=0,
        max_model_runtime_ms=0.0,
        max_execution_duration_ms=0.0,
    )

    gateway = make_gateway(
        budget
    )

    gateway.enforce_budget = False

    agent = FakeAgent(
        [
            make_turn(
                content="Completed.",
                input_tokens=100,
                output_tokens=100,
                model_latency_ms=100.0,
            )
        ]
    )

    result = (
        await run_agent_scenario(
            make_scenario(
                "BUDGET-DISABLED"
            ),
            agent,
            gateway_factory=(
                lambda: gateway
            ),
        )
    )

    assert (
        result.actual_outcome
        == "ALLOW"
    )

    assert (
        budget.snapshots()
        == {}
    )