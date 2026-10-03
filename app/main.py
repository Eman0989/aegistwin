from dataclasses import asdict
from time import perf_counter
from typing import Any

from fastapi import FastAPI, HTTPException, Response
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.audit import AuditLog, infer_control
from app.config import (
    ACTIVE_POLICY,
    MAX_ESTIMATED_COST,
    MAX_EXTERNAL_HTTP_CALLS,
    MAX_TOOL_CALLS,
    SEMANTIC_THRESHOLD,
)
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
from app.security.semantic import (
    HybridSemanticDetector,
)
from app.store import InMemoryStore
from app.telemetry import RuntimeTelemetry
from app.twin.api_analysis import (
    build_twin_analysis,
)


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


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


store = InMemoryStore()
runtime_telemetry = RuntimeTelemetry()
audit_log = AuditLog()
approval_manager = ApprovalManager(store)

budget_manager = BudgetManager(
    max_tool_calls=MAX_TOOL_CALLS,
    max_external_http_calls=(
        MAX_EXTERNAL_HTTP_CALLS
    ),
    max_estimated_cost=MAX_ESTIMATED_COST,
)

runtime_policy_engine = PolicyEngine()

semantic_detector = HybridSemanticDetector(
    threshold=SEMANTIC_THRESHOLD,
)

production_gateway = Gateway(
    runtime_policy_engine,
    store=store,
    approval_manager=approval_manager,
    budget_manager=budget_manager,
    semantic_detector=semantic_detector,
    enforce_tool_allow_list=(
        ACTIVE_POLICY.controls.tool_allow_list
    ),
    enforce_semantic=(
        ACTIVE_POLICY.controls.semantic_detection
    ),
    enforce_composition=(
        ACTIVE_POLICY.controls.composition_analysis
    ),
    enforce_deterministic_policy=(
        ACTIVE_POLICY.controls.deterministic_policy
    ),
    enforce_human_approval=(
        ACTIVE_POLICY.controls.human_approval
    ),
    enforce_budget=(
        ACTIVE_POLICY.controls.budget_enforcement
    ),
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
        semantic_detector=semantic_detector,
        enforce_tool_allow_list=(
            ACTIVE_POLICY.controls.tool_allow_list
        ),
        enforce_semantic=(
            ACTIVE_POLICY.controls.semantic_detection
        ),
        enforce_composition=False,
        enforce_deterministic_policy=(
            ACTIVE_POLICY.controls.deterministic_policy
        ),
        enforce_human_approval=(
            ACTIVE_POLICY.controls.human_approval
        ),
        enforce_budget=(
            ACTIVE_POLICY.controls.budget_enforcement
        ),
    )


@app.get("/health")
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": app.title,
        "version": app.version,
        "contract": "v1.0",
    }


@app.get("/policy")
async def get_policy() -> dict[str, Any]:
    """Expose the validated startup policy to the dashboard."""

    return jsonable_encoder(
        {
            "status": "validated",
            "source": "policies/aegis.yaml",
            "policy": ACTIVE_POLICY,
            "enforcement": {
                "organization_ceilings": (
                    "non_overridable"
                ),
                "validation": (
                    "pydantic-and-hard-coded-ceilings"
                ),
                "load_time": "application_startup",
            },
            "reload_mode": "startup",
            "hot_reload": False,
        }
    )


@app.get("/capabilities")
async def capabilities() -> dict[str, Any]:
    return {
        "architecture": "hybrid-control-layer",
        "gateway_mode": "proxy",
        "composition_enforcement": True,
        "policy_source": "policies/aegis.yaml",
        "policy_version": ACTIVE_POLICY.version,
        "controls": {
            "tool_allow_list": {
                "enabled": (
                    ACTIVE_POLICY
                    .controls
                    .tool_allow_list
                ),
                "type": "deterministic",
            },
            "semantic_injection_detection": {
                "enabled": (
                    ACTIVE_POLICY
                    .controls
                    .semantic_detection
                ),
                "type": "semantic",
                "threshold": SEMANTIC_THRESHOLD,
            },
            "session_composition_analysis": {
                "enabled": (
                    ACTIVE_POLICY
                    .controls
                    .composition_analysis
                ),
                "type": "hybrid",
            },
            "deterministic_policy": {
                "enabled": (
                    ACTIVE_POLICY
                    .controls
                    .deterministic_policy
                ),
                "type": "deterministic",
            },
            "data_lineage": {
                "enabled": (
                    ACTIVE_POLICY
                    .controls
                    .data_lineage
                ),
                "type": "deterministic",
            },
            "budget_enforcement": {
                "enabled": (
                    ACTIVE_POLICY
                    .controls
                    .budget_enforcement
                ),
                "type": "deterministic",
                "max_tool_calls_per_session": (
                    MAX_TOOL_CALLS
                ),
                "max_external_http_calls_per_session": (
                    MAX_EXTERNAL_HTTP_CALLS
                ),
                "max_estimated_cost_per_session": (
                    MAX_ESTIMATED_COST
                ),
            },
            "action_bound_approval": {
                "enabled": (
                    ACTIVE_POLICY
                    .controls
                    .human_approval
                ),
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

    started = perf_counter()

    decision, receipt = await production_gateway.process(
        request.call,
        request.input_artifacts,
        approval_id=request.approval_id,
        estimated_cost=request.estimated_cost,
    )

    latency_ms = (
        perf_counter() - started
    ) * 1000.0

    executed = receipt is not None

    runtime_telemetry.record(
        action=decision.action,
        executed=executed,
        latency_ms=latency_ms,
    )

    audit_log.record(
        timestamp=request.call.timestamp,
        session_id=request.call.session_id,
        call_id=request.call.call_id,
        tool_name=request.call.tool_name,
        instruction_origin=(
            request.call.instruction_origin.value
        ),
        control=infer_control(
            reason=decision.reason,
            action=decision.action,
            executed=executed,
        ),
        action=decision.action,
        reason=decision.reason,
        risk=decision.risk_level,
        latency_ms=latency_ms,
        executed=executed,
        decision_id=decision.decision_id,
        receipt_id=(
            receipt.receipt_id
            if receipt is not None
            else None
        ),
        policy_version=ACTIVE_POLICY.version,
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
            "executed": executed,
            "receipt": receipt,
            "session": snapshot,
            "composition_analysis": latest_composition,
            "policy_version": ACTIVE_POLICY.version,
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

    response = report.as_dict()
    response["policy_version"] = (
        ACTIVE_POLICY.version
    )

    return jsonable_encoder(response)


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
            "policy_version": ACTIVE_POLICY.version,
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

    twin_analysis = build_twin_analysis(
        receipts=replay["before"].receipts,
        legitimate_receipts=(
            replay["legitimate_after"].receipts
        ),
    )

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
                    before_metrics
                    .false_positive_rate
                ),
                "after": (
                    after_metrics
                    .false_positive_rate
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
            "twin_analysis": twin_analysis,
            "policy_version": ACTIVE_POLICY.version,
        }
    )

    return jsonable_encoder(response)


@app.get("/audit/events")
async def audit_events() -> dict[str, Any]:
    """Return process-local gateway audit events."""

    events = audit_log.list_event_dicts()

    return jsonable_encoder(
        {
            "status": "ok",
            "policy_version": ACTIVE_POLICY.version,
            "event_count": len(events),
            "events": events,
        }
    )


@app.get("/audit/export")
async def audit_export(
    format: str = "json",
) -> Any:
    """Export gateway audit evidence as JSON or CSV."""

    normalized_format = format.strip().lower()

    if normalized_format == "json":
        return jsonable_encoder(
            audit_log.export_json()
        )

    if normalized_format == "csv":
        return Response(
            content=audit_log.export_csv(),
            media_type="text/csv",
            headers={
                "Content-Disposition": (
                    "attachment; "
                    'filename="aegistwin-audit.csv"'
                )
            },
        )

    raise HTTPException(
        status_code=400,
        detail=(
            "Unsupported audit export format. "
            "Use 'json' or 'csv'."
        ),
    )


@app.get("/telemetry")
async def telemetry() -> dict[str, Any]:
    """Expose management and security telemetry."""

    metrics = runtime_telemetry.snapshot()

    return jsonable_encoder(
        {
            "status": "ok",
            "policy_version": ACTIVE_POLICY.version,
            "metrics": metrics,
            "audit": {
                "session_count": len(
                    store.sessions
                ),
                "receipt_count": len(
                    store.receipts
                ),
                "decision_count": len(
                    store.decisions
                ),
                "guardrail_count": len(
                    store.guardrails
                ),
                "pending_approvals": sum(
                    getattr(
                        approval,
                        "status",
                        None,
                    )
                    == ApprovalStatus.PENDING
                    for approval
                    in store.approvals.values()
                ),
                "audit_event_count": len(
                    audit_log.list_events()
                ),
            },
            "controls": {
                "tool_allow_list": (
                    production_gateway
                    .enforce_tool_allow_list
                ),
                "semantic_detection": (
                    production_gateway
                    .enforce_semantic
                ),
                "composition_analysis": (
                    production_gateway
                    .enforce_composition
                ),
                "deterministic_policy": (
                    production_gateway
                    .enforce_deterministic_policy
                ),
                "human_approval": (
                    production_gateway
                    .enforce_human_approval
                ),
                "budget_enforcement": (
                    production_gateway
                    .enforce_budget
                ),
            },
        }
    )


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
    runtime_telemetry.reset()
    audit_log.reset()

    return {
        "status": "ok",
        "message": "Runtime state reset.",
    }