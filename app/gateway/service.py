from collections.abc import Awaitable, Callable
from uuid import uuid4

from app.config import MVP_TOOLS
from app.contracts import (
    DataArtifact,
    DecisionAction,
    EffectReceipt,
    ObservedEffect,
    PolicyDecision,
    RiskLevel,
    ToolCall,
)
from app.controls.approvals import ApprovalManager
from app.controls.budget import BudgetManager
from app.controls.policy import PolicyEngine
from app.gateway.executor import execute_tool
from app.security.composition import (
    SessionCompositionAnalyzer,
)
from app.security.redaction import (
    RedactionResult,
    redact_artifacts,
)
from app.security.semantic import (
    HybridSemanticDetector,
    SemanticDetector,
)
from app.store import InMemoryStore


Executor = Callable[
    [ToolCall, list[DataArtifact]],
    Awaitable[EffectReceipt],
]


class Gateway:
    def __init__(
        self,
        policy_engine: PolicyEngine,
        *,
        store: InMemoryStore | None = None,
        approval_manager: ApprovalManager | None = None,
        budget_manager: BudgetManager | None = None,
        semantic_detector: SemanticDetector | None = None,
        composition_analyzer: SessionCompositionAnalyzer | None = None,
        enforce_tool_allow_list: bool = True,
        enforce_semantic: bool = True,
        enforce_composition: bool = False,
        enforce_deterministic_policy: bool = True,
        enforce_human_approval: bool = True,
        enforce_budget: bool = True,
        executor: Executor | None = None,
    ) -> None:
        self.policy_engine = policy_engine

        if (
            store is not None
            and approval_manager is not None
            and approval_manager.store is not store
        ):
            raise ValueError(
                "Gateway and approval manager must use the same store."
            )

        self.store = (
            store
            or (
                approval_manager.store
                if approval_manager
                else InMemoryStore()
            )
        )

        self.approval_manager = (
            approval_manager
            or ApprovalManager(self.store)
        )

        self.budget_manager = (
            budget_manager
            or BudgetManager()
        )

        self.semantic_detector = (
            semantic_detector
            or HybridSemanticDetector()
        )

        self.composition_analyzer = (
            composition_analyzer
            or SessionCompositionAnalyzer()
        )

        self.enforce_tool_allow_list = (
            enforce_tool_allow_list
        )

        self.enforce_semantic = enforce_semantic
        self.enforce_composition = enforce_composition

        self.enforce_deterministic_policy = (
            enforce_deterministic_policy
        )

        self.enforce_human_approval = (
            enforce_human_approval
        )

        self.enforce_budget = enforce_budget

        self.executor = executor or execute_tool

    async def process(
        self,
        call: ToolCall,
        input_artifacts: list[DataArtifact] | None = None,
        *,
        approval_id: str | None = None,
        estimated_cost: float = 0.0,
    ) -> tuple[
        PolicyDecision,
        EffectReceipt | None,
    ]:
        inputs = list(input_artifacts or [])

        execution_inputs = list(inputs)

        redaction_result: (
            RedactionResult | None
        ) = None

        self._ensure_session(call.session_id)

        # --------------------------------------------------
        # Boundary 1: registered-tool allow-list
        # --------------------------------------------------

        if (
            self.enforce_tool_allow_list
            and call.tool_name not in MVP_TOOLS
        ):
            decision = self._new_decision(
                call,
                DecisionAction.BLOCK,
                (
                    f"Unsupported tool '{call.tool_name}'; "
                    "only MVP tools may execute."
                ),
                risk_level=RiskLevel.HIGH,
            )

            return (
                self._record_decision(
                    decision,
                    call.session_id,
                ),
                None,
            )

        # --------------------------------------------------
        # Boundary 2: single-call semantic analysis
        # --------------------------------------------------

        if self.enforce_semantic:
            semantic_verdict = (
                self.semantic_detector.analyze(
                    call
                )
            )

            if semantic_verdict.malicious:
                decision = self._new_decision(
                    call,
                    DecisionAction.BLOCK,
                    (
                        "Semantic control blocked "
                        f"{semantic_verdict.category}: "
                        f"{semantic_verdict.reason} "
                        "Confidence="
                        f"{semantic_verdict.score:.2f}; "
                        "engine="
                        f"{semantic_verdict.engine}."
                    ),
                    risk_level=(
                        semantic_verdict.risk_level
                    ),
                )

                return (
                    self._record_decision(
                        decision,
                        call.session_id,
                    ),
                    None,
                )

        # --------------------------------------------------
        # Boundary 3: session composition analysis
        # --------------------------------------------------

        session_receipts = (
            self.store.list_receipts_for_session(
                call.session_id
            )
        )

        composition_verdict = (
            self.composition_analyzer.analyze(
                receipts=session_receipts,
                proposed_call=call,
                input_artifacts=inputs,
            )
        )

        self._save_composition_analysis(
            call.session_id,
            composition_verdict.as_dict(),
        )

        if (
            self.enforce_composition
            and composition_verdict.dangerous
        ):
            decision = self._new_decision(
                call,
                DecisionAction.BLOCK,
                (
                    "Session composition control blocked "
                    f"{composition_verdict.category}: "
                    f"{composition_verdict.reason} "
                    "Confidence="
                    f"{composition_verdict.score:.2f}; "
                    "path="
                    f"{' -> '.join(composition_verdict.tool_sequence)}."
                ),
                risk_level=(
                    composition_verdict.risk_level
                ),
            )

            return (
                self._record_decision(
                    decision,
                    call.session_id,
                ),
                None,
            )

        # --------------------------------------------------
        # Boundary 4: deterministic policy evaluation
        # --------------------------------------------------

        labels = (
            set().union(
                *(
                    artifact.labels
                    for artifact in inputs
                )
            )
            if inputs
            else set()
        )

        destination = (
            "EXTERNAL"
            if call.tool_name == "external_http"
            else None
        )

        if self.enforce_deterministic_policy:
            decision = self.policy_engine.evaluate(
                call,
                labels,
                destination,
            )
        else:
            decision = self._new_decision(
                call,
                DecisionAction.ALLOW,
                (
                    "Deterministic policy control is "
                    "disabled by startup configuration."
                ),
            )

        if decision.action == DecisionAction.BLOCK:
            return (
                self._record_decision(
                    decision,
                    call.session_id,
                ),
                None,
            )

        # --------------------------------------------------
        # Boundary 5A: deterministic redaction
        # --------------------------------------------------

        if decision.action == DecisionAction.REDACT:
            redaction_result = redact_artifacts(
                inputs
            )

            if not redaction_result.changed:
                blocked = self._new_decision(
                    call,
                    DecisionAction.BLOCK,
                    (
                        "Policy required redaction, but "
                        "no redactable sensitive value "
                        "was identified. Execution stopped "
                        "safely."
                    ),
                    risk_level=RiskLevel.HIGH,
                )

                return (
                    self._record_decision(
                        blocked,
                        call.session_id,
                    ),
                    None,
                )

            execution_inputs = (
                redaction_result.artifacts
            )

            decision = self._replace_decision(
                decision,
                reason=(
                    "Policy required redaction; "
                    f"sanitized "
                    f"{redaction_result.redacted_value_count} "
                    "sensitive value(s) across "
                    f"{redaction_result.changed_artifact_count} "
                    "artifact(s) before execution. "
                    f"Policy reason: {decision.reason}"
                ),
            )

        # --------------------------------------------------
        # Boundary 5B: action-bound human approval
        # --------------------------------------------------

        elif (
            decision.action
            == DecisionAction.REQUIRE_APPROVAL
            and self.enforce_human_approval
        ):
            if approval_id is None:
                required = self._replace_decision(
                    decision,
                    reason=(
                        "Human approval required: "
                        f"{decision.reason}"
                    ),
                )

                return (
                    self._record_decision(
                        required,
                        call.session_id,
                    ),
                    None,
                )

            if not self.approval_manager.authorize(
                approval_id,
                call,
            ):
                blocked = self._new_decision(
                    call,
                    DecisionAction.BLOCK,
                    (
                        "Approval is missing, denied, "
                        "expired, replayed, or does not "
                        "match this tool call."
                    ),
                    risk_level=RiskLevel.HIGH,
                )

                return (
                    self._record_decision(
                        blocked,
                        call.session_id,
                    ),
                    None,
                )

            decision = self._replace_decision(
                decision,
                action=DecisionAction.ALLOW,
                reason=(
                    "Human approval validated; "
                    "policy and budget checks passed."
                ),
            )

        elif decision.action != DecisionAction.ALLOW:
            blocked = self._new_decision(
                call,
                DecisionAction.BLOCK,
                (
                    f"Policy action "
                    f"{decision.action.value} "
                    "cannot execute in this gateway."
                ),
                risk_level=RiskLevel.HIGH,
            )

            return (
                self._record_decision(
                    blocked,
                    call.session_id,
                ),
                None,
            )

        # --------------------------------------------------
        # Boundary 6: budget and resource controls
        # --------------------------------------------------

        if self.enforce_budget:
            budget_result = (
                self.budget_manager.consume(
                    call.session_id,
                    call.tool_name,
                    estimated_cost,
                )
            )

            if not budget_result.allowed:
                blocked = self._new_decision(
                    call,
                    DecisionAction.BLOCK,
                    budget_result.reason,
                    risk_level=RiskLevel.HIGH,
                )

                return (
                    self._record_decision(
                        blocked,
                        call.session_id,
                    ),
                    None,
                )

        # --------------------------------------------------
        # Execution
        # --------------------------------------------------

        self._record_decision(
            decision,
            call.session_id,
        )

        receipt = await self.executor(
            call,
            execution_inputs,
        )

        if (
            redaction_result is not None
            and redaction_result.changed
        ):
            receipt.observed_effects.append(
                ObservedEffect(
                    effect_type="REDACTION",
                    resource=call.tool_name,
                    data_labels={"REDACTED"},
                    metadata={
                        "redacted_value_count": (
                            redaction_result
                            .redacted_value_count
                        ),
                        "changed_artifact_count": (
                            redaction_result
                            .changed_artifact_count
                        ),
                        "original_artifact_ids": (
                            redaction_result
                            .original_artifact_ids
                        ),
                        "sanitized_artifact_ids": (
                            redaction_result
                            .sanitized_artifact_ids
                        ),
                    },
                )
            )

        self.store.save_receipt(receipt)

        return decision, receipt

    def _ensure_session(
        self,
        session_id: str,
    ) -> None:
        if (
            self.store.get_session(
                session_id
            )
            is None
        ):
            self.store.create_session(
                session_id
            )

    def _save_composition_analysis(
        self,
        session_id: str,
        analysis: dict,
    ) -> None:
        session = self.store.get_session(
            session_id
        )

        if session is None:
            session = self.store.create_session(
                session_id
            )

        analyses = session.setdefault(
            "composition_analyses",
            [],
        )

        analyses.append(analysis)

    def _record_decision(
        self,
        decision: PolicyDecision,
        session_id: str,
    ) -> PolicyDecision:
        self.store.save_decision(
            decision,
            session_id=session_id,
        )

        return decision

    @staticmethod
    def _new_decision(
        call: ToolCall,
        action: DecisionAction,
        reason: str,
        *,
        risk_level: RiskLevel = RiskLevel.LOW,
    ) -> PolicyDecision:
        return PolicyDecision(
            decision_id=(
                f"DEC-{uuid4().hex[:8]}"
            ),
            call_id=call.call_id,
            action=action,
            reason=reason,
            risk_level=risk_level,
        )

    @staticmethod
    def _replace_decision(
        decision: PolicyDecision,
        *,
        reason: str,
        action: DecisionAction | None = None,
    ) -> PolicyDecision:
        return PolicyDecision(
            decision_id=decision.decision_id,
            call_id=decision.call_id,
            action=(
                action
                or decision.action
            ),
            reason=reason,
            matched_guardrail_id=(
                decision.matched_guardrail_id
            ),
            risk_level=decision.risk_level,
        )