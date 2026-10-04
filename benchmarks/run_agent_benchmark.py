"""Run the AegisTwin benchmark against a live agent model."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.agents.base import BenchmarkAgent
from app.agents.deepseek import DeepSeekBenchmarkAgent
from app.agents.ollama import OllamaBenchmarkAgent
from app.security.agent_benchmark import (
    BenchmarkScenario,
    ScenarioKind,
    load_benchmark_scenarios,
)
from app.security.agent_runner import (
    run_agent_benchmark,
)


DEFAULT_REPORT_DIRECTORY = (
    Path(__file__).resolve().parent
    / "reports"
)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run AegisTwin's security benchmark "
            "against an agent model."
        )
    )

    parser.add_argument(
        "--provider",
        choices=[
            "ollama",
            "deepseek",
        ],
        default="ollama",
        help=(
            "Agent provider. Ollama runs locally "
            "and is the default."
        ),
    )

    parser.add_argument(
        "--model",
        default=None,
        help=(
            "Optional model override. The default "
            "is llama3.2:3b for Ollama."
        ),
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help=(
            "JSON output path. By default, a "
            "timestamped report is created."
        ),
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help=(
            "Run only the first N selected scenarios."
        ),
    )

    parser.add_argument(
        "--kind",
        choices=[
            "all",
            ScenarioKind.ATTACK.value,
            ScenarioKind.LEGITIMATE.value,
        ],
        default="all",
        help=(
            "Select all, attack, or legitimate cases."
        ),
    )

    parser.add_argument(
        "--category",
        action="append",
        default=[],
        help=(
            "Run only a category. Repeat this option "
            "to select multiple categories."
        ),
    )

    return parser.parse_args()


def select_scenarios(
    scenarios: list[BenchmarkScenario],
    *,
    kind: str,
    categories: list[str],
    limit: int | None,
) -> list[BenchmarkScenario]:
    selected = list(scenarios)

    if kind != "all":
        selected = [
            scenario
            for scenario in selected
            if scenario.kind.value == kind
        ]

    if categories:
        selected_categories = set(
            categories
        )

        selected = [
            scenario
            for scenario in selected
            if scenario.category
            in selected_categories
        ]

    if limit is not None:
        if limit <= 0:
            raise ValueError(
                "--limit must be greater than zero."
            )

        selected = selected[:limit]

    if not selected:
        raise ValueError(
            "No benchmark scenarios matched "
            "the selected filters."
        )

    return selected


def build_agent(
    *,
    provider: str,
    model: str | None,
) -> BenchmarkAgent:
    if provider == "ollama":
        return OllamaBenchmarkAgent(
            model=model,
        )

    if provider == "deepseek":
        api_key = os.getenv(
            "DEEPSEEK_API_KEY",
            "",
        ).strip()

        if not api_key:
            raise RuntimeError(
                "DEEPSEEK_API_KEY is not configured. "
                "Use --provider ollama for a free "
                "local benchmark."
            )

        return DeepSeekBenchmarkAgent(
            api_key=api_key,
            model=model,
        )

    raise ValueError(
        f"Unsupported provider: {provider}"
    )


def default_output_path(
    provider: str,
    model_name: str,
) -> Path:
    timestamp = datetime.now(
        timezone.utc
    ).strftime("%Y%m%dT%H%M%SZ")

    safe_model_name = (
        model_name
        .replace("/", "-")
        .replace(":", "-")
    )

    return (
        DEFAULT_REPORT_DIRECTORY
        / (
            f"{provider}-{safe_model_name}-"
            f"{timestamp}.json"
        )
    )


def build_output(
    *,
    report: Any,
    selected_scenarios: list[
        BenchmarkScenario
    ],
    agent: BenchmarkAgent,
    provider: str,
) -> dict[str, Any]:
    return {
        "benchmark": {
            "name": (
                "AegisTwin Agent Security Benchmark"
            ),
            "generated_at": datetime.now(
                timezone.utc
            ).isoformat(),
            "provider": provider,
            "agent_model": agent.model_name,
            "scenario_count": len(
                selected_scenarios
            ),
            "attack_cases": sum(
                scenario.kind
                == ScenarioKind.ATTACK
                for scenario
                in selected_scenarios
            ),
            "legitimate_cases": sum(
                scenario.kind
                == ScenarioKind.LEGITIMATE
                for scenario
                in selected_scenarios
            ),
            "categories": sorted(
                {
                    scenario.category
                    for scenario
                    in selected_scenarios
                }
            ),
        },
        "report": report.as_dict(),
    }


def print_summary(
    output: dict[str, Any],
    output_path: Path,
) -> None:
    benchmark = output["benchmark"]
    report = output["report"]
    metrics = report["metrics"]

    print()
    print("AEGISTWIN AGENT BENCHMARK")
    print("=" * 44)
    print(
        "PROVIDER:",
        benchmark["provider"],
    )
    print(
        "MODEL:",
        benchmark["agent_model"],
    )
    print(
        "TOTAL CASES:",
        benchmark["scenario_count"],
    )
    print(
        "ATTACK CASES:",
        benchmark["attack_cases"],
    )
    print(
        "LEGITIMATE CASES:",
        benchmark["legitimate_cases"],
    )
    print(
        "ATTACK SUCCESS RATE:",
        f"{metrics['attack_success_rate'] * 100:.2f}%",
    )
    print(
        "UTILITY:",
        f"{metrics['utility'] * 100:.2f}%",
    )
    print(
        "FALSE-POSITIVE RATE:",
        f"{metrics['false_positive_rate'] * 100:.2f}%",
    )
    print(
        "FRICTION:",
        f"{metrics['friction'] * 100:.2f}%",
    )
    print(
        "ESTIMATED API COST:",
        f"${metrics['total_estimated_cost']:.6f}",
    )
    print(
        "PASSED:",
        report["passed"],
    )
    print(
        "REPORT:",
        output_path,
    )


async def run() -> None:
    arguments = parse_arguments()

    agent = build_agent(
        provider=arguments.provider,
        model=arguments.model,
    )

    scenarios = select_scenarios(
        load_benchmark_scenarios(),
        kind=arguments.kind,
        categories=arguments.category,
        limit=arguments.limit,
    )

    output_path = (
        arguments.output
        if arguments.output is not None
        else default_output_path(
            arguments.provider,
            agent.model_name,
        )
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    print(
        "Running",
        len(scenarios),
        "scenario(s) against",
        agent.model_name,
    )

    if arguments.provider == "ollama":
        print(
            "Provider: local Ollama "
            "(no API cost)."
        )
    else:
        print(
            "Provider: DeepSeek API."
        )

    report = await run_agent_benchmark(
        agent,
        scenarios=scenarios,
    )

    output = build_output(
        report=report,
        selected_scenarios=scenarios,
        agent=agent,
        provider=arguments.provider,
    )

    output_path.write_text(
        json.dumps(
            output,
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    print_summary(
        output,
        output_path,
    )


def main() -> None:
    try:
        asyncio.run(run())
    except (
        RuntimeError,
        ValueError,
    ) as error:
        raise SystemExit(
            f"Benchmark error: {error}"
        ) from error


if __name__ == "__main__":
    main()