from dataclasses import asdict
from typing import Any

from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware

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
from app.security.replay import (
    run_attack_repair_replay,
)
from app.store import InMemoryStore
from app.twin.api_analysis import (
    build_twin_analysis,
)


app = FastAPI(
    title="AegisTwin MVP",
    version="1.0.0",
)


# ------------------------------------------------------
# FRONTEND CORS
# ------------------------------------------------------
#
# Vite normally runs on port 5173.
# Port 3000 is also allowed in case the frontend later
# uses another React dev server.
# ------------------------------------------------------

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
approval_manager = ApprovalManager(
    store
)
budget_manager = BudgetManager()


def _runtime_gateway_factory(
    policy_engine: PolicyEngine,
) -> Gateway:
    return Gateway(
        policy_engine,
        store=store,
        approval_manager=(
            approval_manager
        ),
        budget_manager=(
            budget_manager
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


@app.post("/attack-my-agent")
async def attack_my_agent() -> dict[
    str,
    Any,
]:
    # --------------------------------------------------
    # EXISTING ATTACK → REPAIR → REPLAY PIPELINE
    # --------------------------------------------------

    replay = (
        await run_attack_repair_replay(
            gateway_factory=(
                _runtime_gateway_factory
            )
        )
    )

    report = build_benchmark_report(
        replay
    )

    attack = replay[
        "before"
    ].attack_path

    if attack is None:
        raise RuntimeError(
            "Canonical attack path is "
            "missing from the replay result."
        )

    before_metrics = (
        report.before_metrics
    )

    after_metrics = (
        report.after_metrics
    )

    # --------------------------------------------------
    # COMPLETE TWIN INTELLIGENCE EXPOSURE
    # --------------------------------------------------
    #
    # The analysis is generated from the real receipts
    # captured during the vulnerable workflow and the
    # legitimate regression workflow.
    # --------------------------------------------------

    twin_analysis = (
        build_twin_analysis(
            receipts=(
                replay[
                    "before"
                ].receipts
            ),
            legitimate_receipts=(
                replay[
                    "legitimate_after"
                ].receipts
            ),
        )
    )

    # --------------------------------------------------
    # EXISTING RESPONSE + TWIN ANALYSIS
    # --------------------------------------------------

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
                    before_metrics.friction
                ),
                "after": (
                    after_metrics.friction
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

            # ------------------------------------------
            # NEW FRONTEND-FACING TWIN OUTPUT
            # ------------------------------------------

            "twin_analysis": (
                twin_analysis
            ),
        }
    )

    return jsonable_encoder(
        response
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

    return {
        "status": "ok",
        "message": (
            "Runtime state reset."
        ),
    }