from collections.abc import Awaitable, Callable
from time import perf_counter
from typing import Any

from app.contracts import WorkflowResult
from app.controls.policy import PolicyEngine
from app.demo.scenario import run_legitimate_workflow, run_malicious_workflow
from app.security.compiler import compile_guardrail

ScenarioRunner = Callable[[PolicyEngine], Awaitable[WorkflowResult]]
Timer = Callable[[], float]


async def _run_timed(
    runner: ScenarioRunner,
    policy: PolicyEngine,
    timer: Timer,
) -> tuple[WorkflowResult, float]:
    started = timer()
    result = await runner(policy)
    elapsed_ms = max(0.0, (timer() - started) * 1000)
    return result, elapsed_ms


async def run_attack_repair_replay(
    *,
    malicious_runner: ScenarioRunner = run_malicious_workflow,
    legitimate_runner: ScenarioRunner = run_legitimate_workflow,
    timer: Timer = perf_counter,
) -> dict[str, Any]:
    policy = PolicyEngine()
    before, before_attack_ms = await _run_timed(malicious_runner, policy, timer)
    if before.attack_path is None:
        raise RuntimeError("Canonical attack was not reproduced")

    legitimate_before, legitimate_before_ms = await _run_timed(
        legitimate_runner, policy, timer
    )
    guardrail = compile_guardrail(before.attack_path)
    policy.install(guardrail)
    after, after_attack_ms = await _run_timed(malicious_runner, policy, timer)
    legitimate_after, legitimate_after_ms = await _run_timed(
        legitimate_runner, policy, timer
    )

    regression_passed = (
        after.blocked
        and legitimate_after.success
        and not legitimate_after.blocked
    )

    return {
        "before": before,
        "generated_guardrail": guardrail,
        "after": after,
        "legitimate_regression": legitimate_after,
        "legitimate_before": legitimate_before,
        "legitimate_after": legitimate_after,
        "case_timings_ms": {
            "before_attack": before_attack_ms,
            "before_legitimate": legitimate_before_ms,
            "after_attack": after_attack_ms,
            "after_legitimate": legitimate_after_ms,
        },
        "regression_suite_passed": regression_passed,
        "summary": {
            "attack_before": "SUCCESSFUL" if not before.blocked else "BLOCKED",
            "attack_after": "BLOCKED" if after.blocked else "SUCCESSFUL",
            "legitimate_task": "ALLOWED" if legitimate_after.success else "BLOCKED",
        },
    }
