import json
from pathlib import Path

import httpx
import pytest

from app.agents.base import (
    AgentMessage,
    AgentToolDefinition,
    ScriptedBenchmarkAgent,
)
from app.agents.deepseek import (
    DeepSeekBenchmarkAgent,
)
from app.security.agent_benchmark import (
    AgentBenchmarkCaseResult,
    BenchmarkScenario,
    ExpectedOutcome,
    ScenarioKind,
    build_agent_benchmark_report,
    load_benchmark_scenarios,
    load_scenario_file,
)


def make_result(
    *,
    scenario_id: str,
    kind: str,
    category: str,
    correctly_handled: bool,
    attack_succeeded: bool = False,
    legitimate_task_completed: bool = False,
    false_positive: bool = False,
    required_approval: bool = False,
    gateway_latency_ms: float = 2.0,
    model_latency_ms: float = 10.0,
    estimated_cost: float = 0.001,
) -> AgentBenchmarkCaseResult:
    return AgentBenchmarkCaseResult(
        scenario_id=scenario_id,
        name=scenario_id,
        category=category,
        kind=kind,
        expected_outcome=(
            "BLOCK"
            if kind == "attack"
            else "ALLOW"
        ),
        actual_outcome=(
            "BLOCK"
            if correctly_handled
            and kind == "attack"
            else "ALLOW"
        ),
        correctly_handled=correctly_handled,
        attack_succeeded=attack_succeeded,
        legitimate_task_completed=(
            legitimate_task_completed
        ),
        false_positive=false_positive,
        required_approval=required_approval,
        attempted_tool_calls=1,
        executed_tool_calls=(
            0
            if kind == "attack"
            else 1
        ),
        gateway_latency_ms=gateway_latency_ms,
        model_latency_ms=model_latency_ms,
        end_to_end_latency_ms=(
            gateway_latency_ms
            + model_latency_ms
        ),
        input_tokens=100,
        output_tokens=20,
        estimated_cost=estimated_cost,
        model_name="test-model",
        reason="Test result.",
    )


def test_loads_attack_and_legitimate_scenarios() -> None:
    scenarios = load_benchmark_scenarios()

    attacks = [
        scenario
        for scenario in scenarios
        if scenario.kind == ScenarioKind.ATTACK
    ]

    legitimate = [
        scenario
        for scenario in scenarios
        if scenario.kind
        == ScenarioKind.LEGITIMATE
    ]

    assert len(scenarios) == 75
    assert len(attacks) == 50
    assert len(legitimate) == 25

    assert len(
        {
            scenario.scenario_id
            for scenario in scenarios
        }
    ) == 75


def test_attack_scenario_requires_damage_condition() -> None:
    with pytest.raises(
        ValueError,
        match="damage_condition",
    ):
        BenchmarkScenario(
            scenario_id="ATK-INVALID",
            name="Invalid attack",
            category="test",
            kind=ScenarioKind.ATTACK,
            user_task="Attempt an attack.",
            expected_outcome=(
                ExpectedOutcome.BLOCK
            ),
        )


def test_legitimate_scenario_cannot_expect_block() -> None:
    with pytest.raises(
        ValueError,
        match="Legitimate scenarios cannot",
    ):
        BenchmarkScenario(
            scenario_id="LEG-INVALID",
            name="Invalid legitimate case",
            category="test",
            kind=ScenarioKind.LEGITIMATE,
            user_task="Complete a safe task.",
            expected_outcome=(
                ExpectedOutcome.BLOCK
            ),
        )


def test_duplicate_scenario_ids_are_rejected(
    tmp_path: Path,
) -> None:
    attack_path = tmp_path / "attacks.json"

    legitimate_path = (
        tmp_path / "legitimate.json"
    )

    attack_case = {
        "scenario_id": "DUPLICATE-001",
        "name": "Duplicate attack",
        "category": "test",
        "kind": "attack",
        "user_task": "Attempt an attack.",
        "expected_outcome": "BLOCK",
        "damage_condition": "Damage occurs.",
    }

    legitimate_case = {
        "scenario_id": "DUPLICATE-001",
        "name": "Duplicate legitimate case",
        "category": "test",
        "kind": "legitimate",
        "user_task": "Complete a safe task.",
        "expected_outcome": "ALLOW",
    }

    attack_path.write_text(
        json.dumps([attack_case]),
        encoding="utf-8",
    )

    legitimate_path.write_text(
        json.dumps([legitimate_case]),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="IDs must be unique",
    ):
        load_benchmark_scenarios(
            attack_path=attack_path,
            legitimate_path=legitimate_path,
        )


def test_non_list_scenario_file_is_rejected(
    tmp_path: Path,
) -> None:
    scenario_path = tmp_path / "invalid.json"

    scenario_path.write_text(
        json.dumps(
            {
                "scenario_id": "INVALID"
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="JSON list",
    ):
        load_scenario_file(scenario_path)


@pytest.mark.asyncio
async def test_scripted_agent_returns_configured_turns() -> None:
    from app.agents.base import (
        AgentToolCall,
        AgentTurn,
    )

    agent = ScriptedBenchmarkAgent(
        [
            AgentTurn(
                content="Requesting summary.",
                tool_calls=[
                    AgentToolCall(
                        call_id="CALL-1",
                        tool_name="summarizer",
                        arguments={
                            "content": "Invoice"
                        },
                    )
                ],
            )
        ]
    )

    turn = await agent.respond(
        [
            AgentMessage(
                role="user",
                content="Summarize invoice.",
            )
        ],
        [
            AgentToolDefinition(
                name="summarizer",
                description="Summarize text.",
            )
        ],
    )

    assert turn.model_name == (
        "scripted-test-agent"
    )

    assert turn.requested_tool_execution

    assert (
        turn.tool_calls[0].tool_name
        == "summarizer"
    )


@pytest.mark.asyncio
async def test_deepseek_adapter_parses_fake_tool_call() -> None:
    async def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        body = json.loads(
            request.content.decode("utf-8")
        )

        assert body["model"] == (
            "deepseek-flash"
        )

        assert (
            body["tools"][0]["function"]["name"]
            == "summarizer"
        )

        assert (
            request.headers["authorization"]
            == "Bearer test-key"
        )

        return httpx.Response(
            status_code=200,
            json={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "",
                            "tool_calls": [
                                {
                                    "id": "CALL-FAKE-1",
                                    "type": "function",
                                    "function": {
                                        "name": "summarizer",
                                        "arguments": (
                                            '{"content": '
                                            '"Invoice 1042"}'
                                        ),
                                    },
                                }
                            ],
                        }
                    }
                ],
                "usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 20,
                },
            },
        )

    transport = httpx.MockTransport(
        handler
    )

    async with httpx.AsyncClient(
        transport=transport
    ) as client:
        agent = DeepSeekBenchmarkAgent(
            api_key="test-key",
            client=client,
            input_cost_per_million=1.0,
            output_cost_per_million=2.0,
        )

        turn = await agent.respond(
            [
                AgentMessage(
                    role="user",
                    content=(
                        "Summarize invoice 1042."
                    ),
                )
            ],
            [
                AgentToolDefinition(
                    name="summarizer",
                    description="Summarize text.",
                    parameters={
                        "type": "object",
                        "properties": {
                            "content": {
                                "type": "string"
                            }
                        },
                        "required": [
                            "content"
                        ],
                    },
                )
            ],
        )

    assert turn.model_name == (
        "deepseek-flash"
    )

    assert turn.input_tokens == 100
    assert turn.output_tokens == 20
    assert turn.model_latency_ms >= 0
    assert len(turn.tool_calls) == 1

    assert (
        turn.tool_calls[0].tool_name
        == "summarizer"
    )

    assert (
        turn.tool_calls[0].arguments[
            "content"
        ]
        == "Invoice 1042"
    )

    assert turn.estimated_cost == (
        pytest.approx(0.00014)
    )


def test_report_calculates_required_metrics() -> None:
    results = [
        make_result(
            scenario_id="ATK-1",
            kind="attack",
            category="injection",
            correctly_handled=True,
        ),
        make_result(
            scenario_id="ATK-2",
            kind="attack",
            category="jailbreak",
            correctly_handled=True,
        ),
        make_result(
            scenario_id="LEG-1",
            kind="legitimate",
            category="safe_summary",
            correctly_handled=True,
            legitimate_task_completed=True,
        ),
        make_result(
            scenario_id="LEG-2",
            kind="legitimate",
            category="safe_summary",
            correctly_handled=True,
            legitimate_task_completed=True,
        ),
    ]

    report = build_agent_benchmark_report(
        results
    )

    metrics = report.metrics

    assert (
        metrics.attack_success_rate
        == 0.0
    )

    assert metrics.utility == 1.0

    assert (
        metrics.false_positive_rate
        == 0.0
    )

    assert metrics.friction == 0.0
    assert metrics.attack_cases == 2
    assert metrics.legitimate_cases == 2
    assert metrics.total_cases == 4
    assert metrics.attempted_tool_calls == 4
    assert metrics.executed_tool_calls == 2

    assert metrics.total_estimated_cost == (
        pytest.approx(0.004)
    )

    assert metrics.average_cost_per_case == (
        pytest.approx(0.001)
    )

    assert len(
        report.category_metrics
    ) == 3

    assert report.passed