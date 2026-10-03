from dataclasses import asdict
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field

from app.contracts import (
    DataArtifact,
    ToolCall,
)
from app.controls.approvals import (
    ApprovalManager,
    ApprovalStatus,
)
from app.controls.budget import BudgetManager
from app.controls.policy import PolicyEngine
from app.gateway.service import Gateway
from app.security.benchmark import (
    build_benchmark_report,
)
from app.security.benchmark_suite import (
    run_extended_benchmark,
)
from app.security.replay import (
    run_attack_repair_replay,
)
from app.store import InMemoryStore


class GatewayEvaluationRequest(BaseModel):
    call: ToolCall
    input_artifacts: list[DataArtifact] = Field(
        default_factory=list
    )
    approval_id: str | None = None
    estimated_cost: float = 0.0


app = FastAPI(
    title="AegisTwin MVP",
    version="1.0.0",
    description=(
        "Hybrid deterministic and semantic control layer "
        "for agentic AI systems."
    ),
)

store = InMemoryStore()
approval_manager = ApprovalManager(store)
budget_manager = BudgetManager()
runtime_policy_engine = PolicyEngine()

production_gateway = Gateway(
    runtime_policy_engine,
    store=store,
    approval_manager=approval_manager,
    budget_manager=budget_manager,
    enforce_composition=True,
)


def _replay_gateway_factory(
    policy_engine: PolicyEngine,
) -> Gateway:
    """Gateway used for before-and-after attack discovery."""

    return Gateway(
        policy_engine,
        store=store,
        approval_manager=approval_manager,
        budget_manager=budget_manager,
        enforce_composition=False,
    )


@app.get("/health")
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": app.title,
        "version": app.version,
        "contract": "v1.0",
    }


@app.get("/capabilities")
async def capabilities() -> dict[str, Any]:
    return {
        "architecture": "hybrid-control-layer",
        "gateway_mode": "proxy",
        "composition_enforcement": True,
        "controls": {
            "tool_allow_list": {
                "enabled": True,
                "type": "deterministic",
            },
            "semantic_injection_detection": {
                "enabled": True,
                "type": "semantic",
            },
            "session_composition_analysis": {
                "enabled": True,
                "type": "hybrid",
            },
            "deterministic_policy": {
                "enabled": True,
                "type": "deterministic",
            },
            "data_lineage": {
                "enabled": True,
                "type": "deterministic",
            },
            "budget_enforcement": {
                "enabled": True,
                "type": "deterministic",
            },
            "action_bound_approval": {
                "enabled": True,
                "type": "deterministic",
            },
        },
        "decision_actions": [
            "ALLOW",
            "BLOCK",
            "REDACT",
            "REQUIRE_APPROVAL",
        ],
    }


@app.post("/gateway/evaluate")
async def evaluate_gateway(
    request: GatewayEvaluationRequest,
) -> dict[str, Any]:
    """Evaluate and optionally execute one tool call."""

    decision, receipt = await production_gateway.process(
        request.call,
        request.input_artifacts,
        approval_id=request.approval_id,
        estimated_cost=request.estimated_cost,
    )

    snapshot = store.session_snapshot(
        request.call.session_id
    )

    session = store.get_session(
        request.call.session_id
    ) or {}

    composition_analyses = session.get(
        "composition_analyses",
        [],
    )

    latest_composition = (
        composition_analyses[-1]
        if composition_analyses
        else None
    )

    return jsonable_encoder(
        {
            "decision": decision,
            "executed": receipt is not None,
            "receipt": receipt,
            "session": snapshot,
            "composition_analysis": (
                latest_composition
            ),
            "control_path": [
                "tool_allow_list",
                "semantic_detection",
                "session_composition",
                "deterministic_policy",
                "human_approval",
                "budget_control",
                "execution",
            ],
        }
    )


@app.post("/benchmark/extended")
async def extended_benchmark() -> dict[str, Any]:
    """Run the complete positive and negative benchmark suite."""

    report = await run_extended_benchmark()

    return jsonable_encoder(
        report.as_dict()
    )


@app.get("/runtime/sessions/{session_id}")
async def get_runtime_session(
    session_id: str,
) -> dict[str, Any]:
    session = store.get_session(session_id)

    if session is None:
        raise HTTPException(
            status_code=404,
            detail="Session not found.",
        )

    snapshot = store.session_snapshot(session_id)

    return jsonable_encoder(
        {
            "snapshot": snapshot,
            "composition_analyses": session.get(
                "composition_analyses",
                [],
            ),
            "receipts": (
                store.list_receipts_for_session(
                    session_id
                )
            ),
            "decisions": (
                store.list_decisions_for_session(
                    session_id
                )
            ),
        }
    )


@app.post("/attack-my-agent")
async def attack_my_agent() -> dict[str, Any]:
    replay = await run_attack_repair_replay(
        gateway_factory=_replay_gateway_factory
    )

    report = build_benchmark_report(replay)
    attack = replay["before"].attack_path

    if attack is None:
        raise RuntimeError(
            "Canonical attack path is missing "
            "from the replay result."
        )

    before_metrics = report.before_metrics
    after_metrics = report.after_metrics

    response = dict(replay)

    response.update(
        {
            "original_user_intent": (
                attack.original_intent
            ),
            "instruction_origin": (
                attack.instruction_origin.value
            ),
            "sensitive_lineage": sorted(
                attack.source_labels
            ),
            "attack_path": attack.path,
            "attack_path_details": attack,
            "legitimate_workflow": (
                replay["legitimate_after"]
            ),
            "benchmark_report": report,
            "asr_before": before_metrics.asr,
            "asr_after": after_metrics.asr,
            "utility_before": before_metrics.utility,
            "utility_after": after_metrics.utility,
            "false_positive_rate": {
                "before": (
                    before_metrics.false_positive_rate
                ),
                "after": (
                    after_metrics.false_positive_rate
                ),
            },
            "friction": {
                "before": before_metrics.friction,
                "after": after_metrics.friction,
            },
            "measured_latency": {
                "before_ms_per_decision": (
                    before_metrics
                    .latency_per_decision_ms
                ),
                "after_ms_per_decision": (
                    after_metrics
                    .latency_per_decision_ms
                ),
                "added_ms_per_decision": (
                    report.absolute_improvement
                    .added_latency_per_decision_ms
                ),
            },
            "regression_passed": (
                report.regression_suite_passed
            ),
        }
    )

    return jsonable_encoder(response)


@app.get("/runtime/status")
async def runtime_status() -> dict[str, Any]:
    pending_approvals = sum(
        getattr(
            approval,
            "status",
            None,
        )
        == ApprovalStatus.PENDING
        for approval in store.approvals.values()
    )

    session_budgets = {
        session_id: asdict(usage)
        for session_id, usage
        in budget_manager.snapshots().items()
    }

    return {
        "receipts": len(store.receipts),
        "decisions": len(store.decisions),
        "pending_approvals": pending_approvals,
        "session_budgets": session_budgets,
    }


@app.post("/runtime/reset")
async def runtime_reset() -> dict[str, str]:
    store.reset()
    budget_manager.reset()

    return {
        "status": "ok",
        "message": "Runtime state reset.",
    }