"""Judge-facing policy mutation robustness evidence for AegisTwin.

Proves that AegisTwin enforcement is policy-driven rather than
hard-coded by evaluating the exact same request under:

1. Default policy
2. Strict policy
3. Relaxed policy

The request has estimated cost 50.0.

Expected:
- Default limit 100.0 -> ALLOW
- Strict limit 25.0 -> BLOCK
- Relaxed limit 200.0 -> ALLOW
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

from app.contracts import (
    DecisionAction,
    InstructionOrigin,
    ToolCall,
)
from app.controls.budget import BudgetManager
from app.controls.policy import PolicyEngine
from app.gateway.service import Gateway
from app.policy_config import (
    AegisPolicyConfig,
    load_policy_config,
)
from app.security.semantic import (
    HybridSemanticDetector,
)
from app.store import InMemoryStore


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_POLICY = (
    ROOT
    / "policies"
    / "aegis.yaml"
)

STRICT_POLICY = (
    ROOT
    / "policies"
    / "aegis-strict.yaml"
)

RELAXED_POLICY = (
    ROOT
    / "policies"
    / "aegis-relaxed.yaml"
)

TEST_COST = 50.0


@dataclass(frozen=True)
class PolicyCase:
    name: str
    path: Path
    expected_action: DecisionAction


CASES = [
    PolicyCase(
        name="DEFAULT",
        path=DEFAULT_POLICY,
        expected_action=DecisionAction.ALLOW,
    ),
    PolicyCase(
        name="STRICT",
        path=STRICT_POLICY,
        expected_action=DecisionAction.BLOCK,
    ),
    PolicyCase(
        name="RELAXED",
        path=RELAXED_POLICY,
        expected_action=DecisionAction.ALLOW,
    ),
]


def build_gateway(
    policy: AegisPolicyConfig,
) -> Gateway:
    store = InMemoryStore()

    budget_manager = BudgetManager(
        max_tool_calls=(
            policy
            .budgets
            .max_tool_calls_per_session
        ),
        max_external_http_calls=(
            policy
            .budgets
            .max_external_http_calls_per_session
        ),
        max_estimated_cost=(
            policy
            .budgets
            .max_estimated_cost_per_session
        ),
    )

    semantic_detector = (
        HybridSemanticDetector(
            threshold=(
                policy
                .models
                .semantic_threshold
            ),
        )
    )

    return Gateway(
        PolicyEngine(),
        store=store,
        budget_manager=budget_manager,
        semantic_detector=semantic_detector,
        enforce_tool_allow_list=(
            policy
            .controls
            .tool_allow_list
        ),
        enforce_semantic=(
            policy
            .controls
            .semantic_detection
        ),
        enforce_composition=(
            policy
            .controls
            .composition_analysis
        ),
        enforce_deterministic_policy=(
            policy
            .controls
            .deterministic_policy
        ),
        enforce_human_approval=(
            policy
            .controls
            .human_approval
        ),
        enforce_budget=(
            policy
            .controls
            .budget_enforcement
        ),
    )


def build_call(
    policy_name: str,
) -> ToolCall:
    return ToolCall(
        call_id=(
            f"POLICY-ROBUSTNESS-{policy_name}"
        ),
        session_id=(
            f"POLICY-ROBUSTNESS-{policy_name}"
        ),
        tool_name="summarizer",
        arguments={
            "content": (
                "Summarize this approved "
                "internal project report."
            ),
        },
        instruction_origin=(
            InstructionOrigin.USER
        ),
        original_user_intent=(
            "Summarize the approved "
            "internal project report."
        ),
    )


async def run_case(
    case: PolicyCase,
) -> dict:
    policy = load_policy_config(
        case.path
    )

    gateway = build_gateway(
        policy
    )

    decision, receipt = (
        await gateway.process(
            build_call(
                case.name
            ),
            estimated_cost=TEST_COST,
        )
    )

    passed = (
        decision.action
        == case.expected_action
    )

    return {
        "case": case,
        "policy": policy,
        "decision": decision,
        "receipt": receipt,
        "passed": passed,
    }


async def main() -> None:
    print()
    print("=" * 82)
    print(
        "AEGISTWIN — POLICY MUTATION ROBUSTNESS"
    )
    print("=" * 82)
    print(
        "Same request evaluated under "
        "three validated policies"
    )
    print(
        f"Request estimated cost: {TEST_COST:.2f}"
    )
    print("=" * 82)

    results = []

    for case in CASES:
        result = await run_case(
            case
        )

        results.append(
            result
        )

        policy = result["policy"]
        decision = result["decision"]
        receipt = result["receipt"]

        budget_limit = (
            policy
            .budgets
            .max_estimated_cost_per_session
        )

        marker = (
            "PASS"
            if result["passed"]
            else "FAIL"
        )

        executed = (
            receipt is not None
        )

        print(
            f"[{marker}] "
            f"{case.name:<8} "
            f"cost_limit={budget_limit:<7.2f} "
            f"request_cost={TEST_COST:<6.2f} "
            f"decision={decision.action.value:<6} "
            f"executed={executed}"
        )

        print(
            f"         reason={decision.reason}"
        )

    default_result = results[0]
    strict_result = results[1]
    relaxed_result = results[2]

    default_action = (
        default_result[
            "decision"
        ].action
    )

    strict_action = (
        strict_result[
            "decision"
        ].action
    )

    relaxed_action = (
        relaxed_result[
            "decision"
        ].action
    )

    behavior_changed = (
        default_action
        != strict_action
    )

    behavior_restored = (
        relaxed_action
        == default_action
    )

    all_expected = all(
        result["passed"]
        for result in results
    )

    strict_not_executed = (
        strict_result["receipt"]
        is None
    )

    print()
    print("=" * 82)
    print(
        "POLICY MUTATION ROBUSTNESS SUMMARY"
    )
    print("=" * 82)

    print(
        "DEFAULT POLICY RESULT:          "
        f"{default_action.value}"
    )

    print(
        "STRICT POLICY RESULT:           "
        f"{strict_action.value}"
    )

    print(
        "RELAXED POLICY RESULT:          "
        f"{relaxed_action.value}"
    )

    print()

    print(
        "POLICY MUTATION CHANGED BEHAVIOR: "
        f"{'YES' if behavior_changed else 'NO'}"
    )

    print(
        "RELAXED POLICY RESTORED BEHAVIOR: "
        f"{'YES' if behavior_restored else 'NO'}"
    )

    print(
        "STRICT VIOLATION EXECUTED:        "
        f"{'NO' if strict_not_executed else 'YES'}"
    )

    print()

    print("VALIDATED POLICY PARAMETERS:")

    for result in results:
        case = result["case"]
        policy = result["policy"]

        print(
            f"  {case.name:<8} "
            f"cost={policy.budgets.max_estimated_cost_per_session:<7.2f} "
            f"tools={policy.budgets.max_tool_calls_per_session:<4} "
            f"http={policy.budgets.max_external_http_calls_per_session:<3} "
            f"semantic_threshold="
            f"{policy.models.semantic_threshold:.2f}"
        )

    print()
    print("=" * 82)

    passed = (
        all_expected
        and behavior_changed
        and behavior_restored
        and strict_not_executed
    )

    if passed:
        print(
            "AEGISTWIN POLICY MUTATION ROBUSTNESS: "
            "PASSED"
        )
    else:
        print(
            "AEGISTWIN POLICY MUTATION ROBUSTNESS: "
            "NEEDS REVIEW"
        )

    print("=" * 82)

    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())