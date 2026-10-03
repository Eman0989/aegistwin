from collections.abc import Awaitable, Callable

import pytest

from app.config import MVP_TOOLS
from app.contracts import (
    DataArtifact,
    DecisionAction,
    EffectReceipt,
    Guardrail,
    InstructionOrigin,
    PolicyDecision,
    ToolCall,
)
from app.controls.approvals import ApprovalManager, ApprovalStatus
from app.controls.budget import BudgetManager
from app.controls.policy import PolicyEngine
from app.gateway.service import Gateway
from app.store import InMemoryStore


def make_call(
    call_id: str = "CALL-1",
    *,
    tool_name: str = "invoice_reader",
    session_id: str = "SES-1",
) -> ToolCall:
    return ToolCall(
        call_id=call_id,
        session_id=session_id,
        tool_name=tool_name,
        instruction_origin=InstructionOrigin.USER,
        original_user_intent="Summarize invoice",
    )


def require_approval_policy() -> PolicyEngine:
    return PolicyEngine(
        [
            Guardrail(
                guardrail_id="GR-APPROVAL",
                source_labels={"CustomerPII"},
                destination="EXTERNAL",
                action=DecisionAction.REQUIRE_APPROVAL,
                generated_from_attack="ATK-1",
                reason="External transmission of sensitive data requires approval.",
            )
        ]
    )


def sensitive_external_artifacts() -> list[DataArtifact]:
    return [DataArtifact(artifact_id="ART-1", value="private", labels={"CustomerPII"})]


def fake_executor_for(
    calls: list[ToolCall],
) -> Callable[[ToolCall, list[DataArtifact]], Awaitable[EffectReceipt]]:
    async def fake_executor(call: ToolCall, inputs: list[DataArtifact]) -> EffectReceipt:
        calls.append(call)
        return EffectReceipt(
            receipt_id=f"REC-{call.call_id}",
            call=call,
            input_artifact_ids=[artifact.artifact_id for artifact in inputs],
            succeeded=True,
        )

    return fake_executor


@pytest.mark.asyncio
async def test_normal_allowed_execution_persists_decision_and_receipt() -> None:
    store = InMemoryStore()
    executed: list[ToolCall] = []
    gateway = Gateway(PolicyEngine(), store=store, executor=fake_executor_for(executed))
    call = make_call()

    decision, receipt = await gateway.process(call)

    assert decision.action == DecisionAction.ALLOW
    assert "No active guardrail matched" in decision.reason
    assert receipt is not None and receipt.succeeded
    assert executed == [call]
    assert store.get_decision(decision.decision_id) == decision
    assert store.get_receipt(receipt.receipt_id) == receipt
    assert gateway.budget_manager.snapshot(call.session_id).tool_calls == 1


@pytest.mark.asyncio
async def test_hard_policy_block_cannot_be_overridden_by_approval() -> None:
    store = InMemoryStore()
    executed: list[ToolCall] = []
    call = make_call(tool_name="external_http")
    blocked_policy = PolicyEngine(
        [
            Guardrail(
                guardrail_id="GR-BLOCK",
                source_labels={"CustomerPII"},
                destination="EXTERNAL",
                action=DecisionAction.BLOCK,
                generated_from_attack="ATK-1",
                reason="Sensitive data cannot cross the boundary.",
            )
        ]
    )
    approvals = ApprovalManager(store)
    gateway = Gateway(
        blocked_policy,
        store=store,
        approval_manager=approvals,
        executor=fake_executor_for(executed),
    )
    policy_decision = PolicyDecision(
        decision_id="DEC-APPROVAL",
        call_id=call.call_id,
        action=DecisionAction.REQUIRE_APPROVAL,
        reason="Test approval record.",
    )
    request = approvals.create_pending(call, policy_decision)
    assert approvals.approve(request.approval_id)

    blocked_decision, receipt = await gateway.process(
        call,
        sensitive_external_artifacts(),
        approval_id=request.approval_id,
    )

    assert blocked_decision.action == DecisionAction.BLOCK
    assert receipt is None
    assert executed == []
    assert store.approvals[request.approval_id] is request
    assert request.status == ApprovalStatus.APPROVED


@pytest.mark.asyncio
async def test_approval_required_without_approval_does_not_execute() -> None:
    executed: list[ToolCall] = []
    gateway = Gateway(require_approval_policy(), executor=fake_executor_for(executed))

    decision, receipt = await gateway.process(
        make_call(tool_name="external_http"),
        sensitive_external_artifacts(),
    )

    assert decision.action == DecisionAction.REQUIRE_APPROVAL
    assert "Human approval required" in decision.reason
    assert receipt is None
    assert executed == []


@pytest.mark.asyncio
async def test_approved_one_use_execution_blocks_replay() -> None:
    store = InMemoryStore()
    approvals = ApprovalManager(store)
    executed: list[ToolCall] = []
    gateway = Gateway(
        require_approval_policy(),
        store=store,
        approval_manager=approvals,
        executor=fake_executor_for(executed),
    )
    call = make_call(tool_name="external_http")
    inputs = sensitive_external_artifacts()
    approval_decision, _ = await gateway.process(call, inputs)
    request = approvals.create_pending(call, approval_decision)
    assert approvals.approve(request.approval_id)

    allowed_decision, receipt = await gateway.process(call, inputs, approval_id=request.approval_id)
    replay_decision, replay_receipt = await gateway.process(
        call, inputs, approval_id=request.approval_id
    )

    assert allowed_decision.action == DecisionAction.ALLOW
    assert "Human approval validated" in allowed_decision.reason
    assert receipt is not None
    assert replay_decision.action == DecisionAction.BLOCK
    assert "replayed" in replay_decision.reason
    assert replay_receipt is None
    assert executed == [call]
    assert request.status == ApprovalStatus.CONSUMED
    assert len(store.list_receipts()) == 1


@pytest.mark.asyncio
async def test_budget_exhaustion_blocks_before_executor() -> None:
    executed: list[ToolCall] = []
    budget = BudgetManager(max_tool_calls=0)
    gateway = Gateway(PolicyEngine(), budget_manager=budget, executor=fake_executor_for(executed))

    decision, receipt = await gateway.process(make_call())

    assert decision.action == DecisionAction.BLOCK
    assert "Maximum tool calls" in decision.reason
    assert receipt is None
    assert executed == []
    assert budget.snapshot("SES-1").tool_calls == 0


@pytest.mark.asyncio
async def test_non_mvp_tool_is_rejected_before_policy_or_executor() -> None:
    executed: list[ToolCall] = []

    class PolicyMustNotRun(PolicyEngine):
        def evaluate(self, call, labels, destination):
            raise AssertionError("Policy must not run for an unsupported tool.")

    gateway = Gateway(PolicyMustNotRun(), executor=fake_executor_for(executed))
    decision, receipt = await gateway.process(make_call(tool_name="unknown_tool"))

    assert "unknown_tool" not in MVP_TOOLS
    assert decision.action == DecisionAction.BLOCK
    assert "Unsupported tool" in decision.reason
    assert receipt is None
    assert executed == []