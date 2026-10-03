from collections.abc import Awaitable, Callable
from uuid import uuid4

from app.config import MVP_TOOLS
from app.contracts import (
    DataArtifact,
    DecisionAction,
    EffectReceipt,
    PolicyDecision,
    ToolCall,
)
from app.controls.approvals import ApprovalManager
from app.controls.budget import BudgetManager
from app.controls.policy import PolicyEngine
from app.gateway.executor import execute_tool
from app.store import InMemoryStore

Executor = Callable[[ToolCall, list[DataArtifact]], Awaitable[EffectReceipt]]


class Gateway:
    def __init__(
        self,
        policy_engine: PolicyEngine,
        *,
        store: InMemoryStore | None = None,
        approval_manager: ApprovalManager | None = None,
        budget_manager: BudgetManager | None = None,
        executor: Executor | None = None,
    ) -> None:
        self.policy_engine = policy_engine
        if store is not None and approval_manager is not None and approval_manager.store is not store:
            raise ValueError("Gateway and approval manager must use the same store.")
        self.store = store or (approval_manager.store if approval_manager else InMemoryStore())
        self.approval_manager = approval_manager or ApprovalManager(self.store)
        self.budget_manager = budget_manager or BudgetManager()
        self.executor = executor or execute_tool

    async def process(
        self,
        call: ToolCall,
        input_artifacts: list[DataArtifact] | None = None,
        *,
        approval_id: str | None = None,
        estimated_cost: float = 0.0,
    ) -> tuple[PolicyDecision, EffectReceipt | None]:
        inputs = list(input_artifacts or [])

        if call.tool_name not in MVP_TOOLS:
            decision = self._new_decision(
                call,
                DecisionAction.BLOCK,
                f"Unsupported tool '{call.tool_name}'; only MVP tools may execute.",
            )
            return self._record_decision(decision), None

        labels = set().union(*(a.labels for a in inputs)) if inputs else set()
        destination = "EXTERNAL" if call.tool_name == "external_http" else None
        decision = self.policy_engine.evaluate(call, labels, destination)
        if decision.action == DecisionAction.BLOCK:
            return self._record_decision(decision), None

        if decision.action == DecisionAction.REQUIRE_APPROVAL:
            if approval_id is None:
                required = self._replace_decision(
                    decision,
                    reason=f"Human approval required: {decision.reason}",
                )
                return self._record_decision(required), None
            if not self.approval_manager.authorize(approval_id, call):
                blocked = self._new_decision(
                    call,
                    DecisionAction.BLOCK,
                    "Approval is missing, denied, expired, replayed, or does not match this tool call.",
                )
                return self._record_decision(blocked), None
            decision = self._replace_decision(
                decision,
                action=DecisionAction.ALLOW,
                reason="Human approval validated; policy and budget checks passed.",
            )
        elif decision.action != DecisionAction.ALLOW:
            blocked = self._new_decision(
                call,
                DecisionAction.BLOCK,
                f"Policy action {decision.action.value} cannot execute in this gateway.",
            )
            return self._record_decision(blocked), None

        budget_result = self.budget_manager.consume(
            call.session_id,
            call.tool_name,
            estimated_cost,
        )
        if not budget_result.allowed:
            blocked = self._new_decision(call, DecisionAction.BLOCK, budget_result.reason)
            return self._record_decision(blocked), None

        self._record_decision(decision)
        receipt = await self.executor(call, inputs)
        self.store.save_receipt(receipt)
        return decision, receipt

    def _record_decision(self, decision: PolicyDecision) -> PolicyDecision:
        self.store.save_decision(decision)
        return decision

    @staticmethod
    def _new_decision(
        call: ToolCall, action: DecisionAction, reason: str
    ) -> PolicyDecision:
        return PolicyDecision(
            decision_id=f"DEC-{uuid4().hex[:8]}",
            call_id=call.call_id,
            action=action,
            reason=reason,
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
            action=action or decision.action,
            reason=reason,
            matched_guardrail_id=decision.matched_guardrail_id,
            risk_level=decision.risk_level,
        )
