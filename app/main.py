from dataclasses import asdict
from datetime import datetime, timezone
from threading import Lock
from time import perf_counter
from typing import Any

import yaml
from fastapi import (
    FastAPI,
    HTTPException,
    Response,
)
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import app.config as runtime_config
from app.audit import AuditLog, infer_control
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
from app.persistence.sqlite_store import (
    DEFAULT_SQLITE_PATH,
    SQLiteEvidenceStore,
)
from app.policy_config import (
    DEFAULT_POLICY_PATH,
    AegisPolicyConfig,
    load_policy_config,
)
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
from app.telemetry import RuntimeTelemetry
from app.twin.api_analysis import (
    build_twin_analysis,
)


class GatewayEvaluationRequest(BaseModel):
    call: ToolCall

    input_artifacts: list[
        DataArtifact
    ] = Field(
        default_factory=list
    )

    approval_id: str | None = None
    estimated_cost: float = 0.0


app = FastAPI(
    title="AegisTwin MVP",
    version="1.0.0",
    description=(
        "Hybrid deterministic and semantic "
        "control layer for agentic AI systems."
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


POLICY_PATH = DEFAULT_POLICY_PATH

PUBLIC_POLICY_SOURCE = (
    "policies/aegis.yaml"
)

_policy_reload_lock = Lock()

_policy_reload_count = 0

_last_policy_reload_at: (
    str | None
) = None


store = SQLiteEvidenceStore(
    DEFAULT_SQLITE_PATH
)

runtime_telemetry = (
    RuntimeTelemetry()
)

audit_log = AuditLog()

approval_manager = (
    ApprovalManager(store)
)


budget_manager = BudgetManager(
    max_tool_calls=(
        runtime_config.MAX_TOOL_CALLS
    ),
    max_external_http_calls=(
        runtime_config
        .MAX_EXTERNAL_HTTP_CALLS
    ),
    max_estimated_cost=(
        runtime_config
        .MAX_ESTIMATED_COST
    ),
    max_agent_turns=(
        runtime_config
        .MAX_AGENT_TURNS
    ),
    max_input_tokens=(
        runtime_config
        .MAX_INPUT_TOKENS
    ),
    max_output_tokens=(
        runtime_config
        .MAX_OUTPUT_TOKENS
    ),
    max_execution_duration_ms=(
        runtime_config
        .MAX_EXECUTION_DURATION_MS
    ),
    max_model_runtime_ms=(
        runtime_config
        .MAX_MODEL_RUNTIME_MS
    ),
)


runtime_policy_engine = (
    PolicyEngine()
)


semantic_detector = (
    HybridSemanticDetector(
        threshold=(
            runtime_config
            .SEMANTIC_THRESHOLD
        ),
    )
)


production_gateway = Gateway(
    runtime_policy_engine,
    store=store,
    approval_manager=approval_manager,
    budget_manager=budget_manager,
    semantic_detector=semantic_detector,
    enforce_tool_allow_list=(
        runtime_config
        .ACTIVE_POLICY
        .controls
        .tool_allow_list
    ),
    enforce_semantic=(
        runtime_config
        .ACTIVE_POLICY
        .controls
        .semantic_detection
    ),
    enforce_composition=(
        runtime_config
        .ACTIVE_POLICY
        .controls
        .composition_analysis
    ),
    enforce_deterministic_policy=(
        runtime_config
        .ACTIVE_POLICY
        .controls
        .deterministic_policy
    ),
    enforce_human_approval=(
        runtime_config
        .ACTIVE_POLICY
        .controls
        .human_approval
    ),
    enforce_budget=(
        runtime_config
        .ACTIVE_POLICY
        .controls
        .budget_enforcement
    ),
)


def _semantic_threshold() -> float:
    return (
        semantic_detector
        .model
        .threshold
    )


def _set_semantic_threshold(
    threshold: float,
) -> None:
    semantic_detector.model.threshold = (
        threshold
    )


def _apply_runtime_policy(
    policy: AegisPolicyConfig,
) -> None:
    """Atomically apply a validated policy to live controls."""

    previous_policy = (
        runtime_config.ACTIVE_POLICY
    )

    previous_gateway_state = {
        "tool_allow_list": (
            production_gateway
            .enforce_tool_allow_list
        ),
        "semantic": (
            production_gateway
            .enforce_semantic
        ),
        "composition": (
            production_gateway
            .enforce_composition
        ),
        "deterministic": (
            production_gateway
            .enforce_deterministic_policy
        ),
        "human_approval": (
            production_gateway
            .enforce_human_approval
        ),
        "budget": (
            production_gateway
            .enforce_budget
        ),
    }

    previous_budget_limits = {
        "max_tool_calls": (
            budget_manager
            .max_tool_calls
        ),
        "max_external_http_calls": (
            budget_manager
            .max_external_http_calls
        ),
        "max_estimated_cost": (
            budget_manager
            .max_estimated_cost
        ),
        "max_agent_turns": (
            budget_manager
            .max_agent_turns
        ),
        "max_input_tokens": (
            budget_manager
            .max_input_tokens
        ),
        "max_output_tokens": (
            budget_manager
            .max_output_tokens
        ),
        "max_execution_duration_ms": (
            budget_manager
            .max_execution_duration_ms
        ),
        "max_model_runtime_ms": (
            budget_manager
            .max_model_runtime_ms
        ),
    }

    previous_threshold = (
        _semantic_threshold()
    )

    try:
        runtime_config.apply_policy_config(
            policy
        )

        budget_manager.update_limits(
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
            max_agent_turns=(
                policy
                .budgets
                .max_agent_turns_per_session
            ),
            max_input_tokens=(
                policy
                .budgets
                .max_input_tokens_per_session
            ),
            max_output_tokens=(
                policy
                .budgets
                .max_output_tokens_per_session
            ),
            max_execution_duration_ms=(
                policy
                .budgets
                .max_execution_duration_ms_per_session
            ),
            max_model_runtime_ms=(
                policy
                .budgets
                .max_model_runtime_ms_per_session
            ),
        )

        _set_semantic_threshold(
            policy
            .models
            .semantic_threshold
        )

        production_gateway.enforce_tool_allow_list = (
            policy
            .controls
            .tool_allow_list
        )

        production_gateway.enforce_semantic = (
            policy
            .controls
            .semantic_detection
        )

        production_gateway.enforce_composition = (
            policy
            .controls
            .composition_analysis
        )

        production_gateway.enforce_deterministic_policy = (
            policy
            .controls
            .deterministic_policy
        )

        production_gateway.enforce_human_approval = (
            policy
            .controls
            .human_approval
        )

        production_gateway.enforce_budget = (
            policy
            .controls
            .budget_enforcement
        )

    except Exception:
        runtime_config.apply_policy_config(
            previous_policy
        )

        budget_manager.update_limits(
            **previous_budget_limits
        )

        _set_semantic_threshold(
            previous_threshold
        )

        production_gateway.enforce_tool_allow_list = (
            previous_gateway_state[
                "tool_allow_list"
            ]
        )

        production_gateway.enforce_semantic = (
            previous_gateway_state[
                "semantic"
            ]
        )

        production_gateway.enforce_composition = (
            previous_gateway_state[
                "composition"
            ]
        )

        production_gateway.enforce_deterministic_policy = (
            previous_gateway_state[
                "deterministic"
            ]
        )

        production_gateway.enforce_human_approval = (
            previous_gateway_state[
                "human_approval"
            ]
        )

        production_gateway.enforce_budget = (
            previous_gateway_state[
                "budget"
            ]
        )

        raise


def _replay_gateway_factory(
    policy_engine: PolicyEngine,
) -> Gateway:
    """Gateway used for before-and-after attack discovery."""

    policy = (
        runtime_config.ACTIVE_POLICY
    )

    return Gateway(
        policy_engine,
        store=store,
        approval_manager=approval_manager,
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
        enforce_composition=False,
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


@app.get("/health")
async def health() -> dict[
    str,
    str,
]:
    return {
        "status": "ok",
        "service": app.title,
        "version": app.version,
        "contract": "v1.0",
    }


@app.get("/policy")
async def get_policy() -> dict[
    str,
    Any,
]:
    policy = (
        runtime_config.ACTIVE_POLICY
    )

    return jsonable_encoder(
        {
            "status": "validated",
            "source": (
                PUBLIC_POLICY_SOURCE
            ),
            "policy": policy,
            "enforcement": {
                "organization_ceilings": (
                    "non_overridable"
                ),
                "validation": (
                    "pydantic-and-hard-coded-ceilings"
                ),
                "load_time": (
                    "application-startup-and-runtime"
                ),
            },
            "reload_mode": "hot",
            "hot_reload": True,
            "reload_count": (
                _policy_reload_count
            ),
            "last_reloaded_at": (
                _last_policy_reload_at
            ),
        }
    )


@app.post("/policy/reload")
async def reload_policy() -> dict[
    str,
    Any,
]:
    global _policy_reload_count
    global _last_policy_reload_at

    with _policy_reload_lock:
        previous_policy = (
            runtime_config
            .ACTIVE_POLICY
        )

        try:
            candidate = (
                load_policy_config(
                    POLICY_PATH
                )
            )
        except (
            FileNotFoundError,
            ValueError,
            yaml.YAMLError,
        ) as exc:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Policy reload rejected; "
                    "the active policy was not changed. "
                    f"{exc}"
                ),
            ) from exc

        changed = (
            candidate.model_dump(
                mode="json"
            )
            != previous_policy.model_dump(
                mode="json"
            )
        )

        try:
            _apply_runtime_policy(
                candidate
            )
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=(
                    "Policy reload failed during "
                    "runtime application; previous "
                    "policy was restored."
                ),
            ) from exc

        _policy_reload_count += 1

        _last_policy_reload_at = (
            datetime.now(
                timezone.utc
            ).isoformat()
        )

        return jsonable_encoder(
            {
                "status": "reloaded",
                "source": (
                    PUBLIC_POLICY_SOURCE
                ),
                "previous_version": (
                    previous_policy.version
                ),
                "policy_version": (
                    candidate.version
                ),
                "changed": changed,
                "reload_count": (
                    _policy_reload_count
                ),
                "reloaded_at": (
                    _last_policy_reload_at
                ),
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
                "semantic_threshold": (
                    runtime_config
                    .SEMANTIC_THRESHOLD
                ),
                "budgets": {
                    "max_tool_calls_per_session": (
                        budget_manager
                        .max_tool_calls
                    ),
                    "max_external_http_calls_per_session": (
                        budget_manager
                        .max_external_http_calls
                    ),
                    "max_estimated_cost_per_session": (
                        budget_manager
                        .max_estimated_cost
                    ),
                    "max_agent_turns_per_session": (
                        budget_manager
                        .max_agent_turns
                    ),
                    "max_input_tokens_per_session": (
                        budget_manager
                        .max_input_tokens
                    ),
                    "max_output_tokens_per_session": (
                        budget_manager
                        .max_output_tokens
                    ),
                    "max_execution_duration_ms_per_session": (
                        budget_manager
                        .max_execution_duration_ms
                    ),
                    "max_model_runtime_ms_per_session": (
                        budget_manager
                        .max_model_runtime_ms
                    ),
                },
            }
        )


@app.get("/capabilities")
async def capabilities() -> dict[
    str,
    Any,
]:
    policy = (
        runtime_config.ACTIVE_POLICY
    )

    return {
        "architecture": (
            "hybrid-control-layer"
        ),
        "gateway_mode": "proxy",
        "composition_enforcement": (
            production_gateway
            .enforce_composition
        ),
        "policy_source": (
            PUBLIC_POLICY_SOURCE
        ),
        "policy_version": (
            policy.version
        ),
        "persistence": {
            "enabled": True,
            "backend": "sqlite",
        },
        "controls": {
            "tool_allow_list": {
                "enabled": (
                    production_gateway
                    .enforce_tool_allow_list
                ),
                "type": "deterministic",
            },
            "semantic_injection_detection": {
                "enabled": (
                    production_gateway
                    .enforce_semantic
                ),
                "type": "semantic",
                "threshold": (
                    runtime_config
                    .SEMANTIC_THRESHOLD
                ),
            },
            "session_composition_analysis": {
                "enabled": (
                    production_gateway
                    .enforce_composition
                ),
                "type": "hybrid",
            },
            "deterministic_policy": {
                "enabled": (
                    production_gateway
                    .enforce_deterministic_policy
                ),
                "type": "deterministic",
            },
            "data_lineage": {
                "enabled": (
                    policy
                    .controls
                    .data_lineage
                ),
                "type": "deterministic",
            },
            "budget_enforcement": {
                "enabled": (
                    production_gateway
                    .enforce_budget
                ),
                "type": "deterministic",
                "max_tool_calls_per_session": (
                    budget_manager
                    .max_tool_calls
                ),
                "max_external_http_calls_per_session": (
                    budget_manager
                    .max_external_http_calls
                ),
                "max_estimated_cost_per_session": (
                    budget_manager
                    .max_estimated_cost
                ),
                "max_agent_turns_per_session": (
                    budget_manager
                    .max_agent_turns
                ),
                "max_input_tokens_per_session": (
                    budget_manager
                    .max_input_tokens
                ),
                "max_output_tokens_per_session": (
                    budget_manager
                    .max_output_tokens
                ),
                "max_execution_duration_ms_per_session": (
                    budget_manager
                    .max_execution_duration_ms
                ),
                "max_model_runtime_ms_per_session": (
                    budget_manager
                    .max_model_runtime_ms
                ),
            },
            "action_bound_approval": {
                "enabled": (
                    production_gateway
                    .enforce_human_approval
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
) -> dict[
    str,
    Any,
]:
    started = (
        perf_counter()
    )

    decision, receipt = (
        await production_gateway.process(
            request.call,
            request.input_artifacts,
            approval_id=(
                request.approval_id
            ),
            estimated_cost=(
                request.estimated_cost
            ),
        )
    )

    latency_ms = (
        perf_counter()
        - started
    ) * 1000.0

    executed = (
        receipt is not None
    )

    runtime_telemetry.record(
        action=decision.action,
        executed=executed,
        latency_ms=latency_ms,
    )

    audit_log.record(
        timestamp=(
            request.call.timestamp
        ),
        session_id=(
            request.call.session_id
        ),
        call_id=(
            request.call.call_id
        ),
        tool_name=(
            request.call.tool_name
        ),
        instruction_origin=(
            request.call
            .instruction_origin
            .value
        ),
        control=infer_control(
            reason=(
                decision.reason
            ),
            action=(
                decision.action
            ),
            executed=executed,
        ),
        action=decision.action,
        reason=decision.reason,
        risk=decision.risk_level,
        latency_ms=latency_ms,
        executed=executed,
        decision_id=(
            decision.decision_id
        ),
        receipt_id=(
            receipt.receipt_id
            if receipt is not None
            else None
        ),
        policy_version=(
            runtime_config
            .ACTIVE_POLICY
            .version
        ),
    )

    snapshot = (
        store.session_snapshot(
            request.call.session_id
        )
    )

    session = (
        store.get_session(
            request.call.session_id
        )
        or {}
    )

    composition_analyses = (
        session.get(
            "composition_analyses",
            [],
        )
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
            "composition_analysis": (
                latest_composition
            ),
            "policy_version": (
                runtime_config
                .ACTIVE_POLICY
                .version
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
async def extended_benchmark() -> dict[
    str,
    Any,
]:
    report = (
        await run_extended_benchmark()
    )

    response = (
        report.as_dict()
    )

    response[
        "policy_version"
    ] = (
        runtime_config
        .ACTIVE_POLICY
        .version
    )

    return jsonable_encoder(
        response
    )


@app.get(
    "/runtime/sessions/{session_id}"
)
async def get_runtime_session(
    session_id: str,
) -> dict[
    str,
    Any,
]:
    session = (
        store.get_session(
            session_id
        )
    )

    if session is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "Session not found."
            ),
        )

    snapshot = (
        store.session_snapshot(
            session_id
        )
    )

    return jsonable_encoder(
        {
            "snapshot": snapshot,
            "composition_analyses": (
                session.get(
                    "composition_analyses",
                    [],
                )
            ),
            "receipts": (
                store
                .list_receipts_for_session(
                    session_id
                )
            ),
            "decisions": (
                store
                .list_decisions_for_session(
                    session_id
                )
            ),
            "policy_version": (
                runtime_config
                .ACTIVE_POLICY
                .version
            ),
        }
    )


@app.get("/persistence/status")
async def persistence_status() -> dict[
    str,
    Any,
]:
    """Expose durable evidence persistence status."""

    return jsonable_encoder(
        {
            "status": "ok",
            **store.persistence_status(),
        }
    )


@app.post("/attack-my-agent")
async def attack_my_agent() -> dict[
    str,
    Any,
]:
    replay = (
        await run_attack_repair_replay(
            gateway_factory=(
                _replay_gateway_factory
            )
        )
    )

    report = (
        build_benchmark_report(
            replay
        )
    )

    attack = (
        replay["before"]
        .attack_path
    )

    if attack is None:
        raise RuntimeError(
            "Canonical attack path is missing "
            "from the replay result."
        )

    before_metrics = (
        report.before_metrics
    )

    after_metrics = (
        report.after_metrics
    )

    twin_analysis = (
        build_twin_analysis(
            receipts=(
                replay["before"]
                .receipts
            ),
            legitimate_receipts=(
                replay[
                    "legitimate_after"
                ].receipts
            ),
        )
    )

    response = dict(
        replay
    )

    response.update(
        {
            "original_user_intent": (
                attack.original_intent
            ),
            "instruction_origin": (
                attack
                .instruction_origin
                .value
            ),
            "sensitive_lineage": sorted(
                attack.source_labels
            ),
            "attack_path": (
                attack.path
            ),
            "attack_path_details": (
                attack
            ),
            "legitimate_workflow": (
                replay[
                    "legitimate_after"
                ]
            ),
            "benchmark_report": (
                report
            ),
            "asr_before": (
                before_metrics.asr
            ),
            "asr_after": (
                after_metrics.asr
            ),
            "utility_before": (
                before_metrics.utility
            ),
            "utility_after": (
                after_metrics.utility
            ),
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
                "before": (
                    before_metrics
                    .friction
                ),
                "after": (
                    after_metrics
                    .friction
                ),
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
                    report
                    .absolute_improvement
                    .added_latency_per_decision_ms
                ),
            },
            "regression_passed": (
                report
                .regression_suite_passed
            ),
            "twin_analysis": (
                twin_analysis
            ),
            "policy_version": (
                runtime_config
                .ACTIVE_POLICY
                .version
            ),
        }
    )

    return jsonable_encoder(
        response
    )


@app.get("/audit/events")
async def audit_events() -> dict[
    str,
    Any,
]:
    events = (
        audit_log
        .list_event_dicts()
    )

    return jsonable_encoder(
        {
            "status": "ok",
            "policy_version": (
                runtime_config
                .ACTIVE_POLICY
                .version
            ),
            "event_count": (
                len(events)
            ),
            "events": events,
        }
    )


@app.get("/audit/export")
async def audit_export(
    format: str = "json",
) -> Any:
    normalized_format = (
        format
        .strip()
        .lower()
    )

    if (
        normalized_format
        == "json"
    ):
        return jsonable_encoder(
            audit_log.export_json()
        )

    if (
        normalized_format
        == "csv"
    ):
        return Response(
            content=(
                audit_log
                .export_csv()
            ),
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
async def telemetry() -> dict[
    str,
    Any,
]:
    metrics = (
        runtime_telemetry
        .snapshot()
    )

    budget_sessions = {
        session_id: (
            budget_manager
            .usage_vs_limits(
                session_id
            )
        )
        for session_id
        in budget_manager
        .snapshots()
    }

    return jsonable_encoder(
        {
            "status": "ok",
            "policy_version": (
                runtime_config
                .ACTIVE_POLICY
                .version
            ),
            "metrics": metrics,
            "budget_governance": {
                "limits": (
                    budget_manager
                    .limits_snapshot()
                ),
                "sessions": (
                    budget_sessions
                ),
            },
            "audit": {
                "session_count": (
                    len(
                        store.sessions
                    )
                ),
                "receipt_count": (
                    len(
                        store.receipts
                    )
                ),
                "decision_count": (
                    len(
                        store.decisions
                    )
                ),
                "guardrail_count": (
                    len(
                        store.guardrails
                    )
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
                "audit_event_count": (
                    len(
                        audit_log
                        .list_events()
                    )
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
            "policy_reload": {
                "reload_count": (
                    _policy_reload_count
                ),
                "last_reloaded_at": (
                    _last_policy_reload_at
                ),
            },
            "persistence": (
                store.persistence_status()
            ),
        }
    )


@app.get("/runtime/status")
async def runtime_status() -> dict[
    str,
    Any,
]:
    pending_approvals = sum(
        getattr(
            approval,
            "status",
            None,
        )
        == ApprovalStatus.PENDING
        for approval
        in store.approvals.values()
    )

    session_budgets = {
        session_id: asdict(
            usage
        )
        for session_id, usage
        in budget_manager
        .snapshots()
        .items()
    }

    return {
        "receipts": len(
            store.receipts
        ),
        "decisions": len(
            store.decisions
        ),
        "pending_approvals": (
            pending_approvals
        ),
        "session_budgets": (
            session_budgets
        ),
    }


@app.post("/runtime/reset")
async def runtime_reset() -> dict[
    str,
    str,
]:
    store.reset()
    budget_manager.reset()
    runtime_telemetry.reset()
    audit_log.reset()

    return {
        "status": "ok",
        "message": (
            "Runtime state reset."
        ),
    }