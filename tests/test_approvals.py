from datetime import datetime, timedelta, timezone

import pytest

from app.contracts import DecisionAction, InstructionOrigin, PolicyDecision, ToolCall
from app.controls.approvals import ApprovalManager, ApprovalStatus
from app.store import InMemoryStore


def make_call(call_id: str = "CALL-1") -> ToolCall:
    return ToolCall(
        call_id=call_id,
        session_id="SES-1",
        tool_name="external_http",
        arguments={"url": "https://example.invalid"},
        instruction_origin=InstructionOrigin.USER,
        original_user_intent="Send the report",
    )


def make_decision(call_id: str = "CALL-1") -> PolicyDecision:
    return PolicyDecision(
        decision_id="DEC-1",
        call_id=call_id,
        action=DecisionAction.REQUIRE_APPROVAL,
        reason="Sensitive external action requires approval.",
    )


def test_pending_approval_can_be_approved_and_consumed_once() -> None:
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    manager = ApprovalManager(clock=lambda: now)
    call = make_call()
    request = manager.create_pending(call, make_decision())

    assert request.status == ApprovalStatus.PENDING
    assert manager.approve(request.approval_id, now=now)
    assert manager.authorize(request.approval_id, call, now=now)
    assert request.status == ApprovalStatus.CONSUMED
    assert not manager.authorize(request.approval_id, call, now=now)


def test_denied_missing_and_mismatched_approvals_never_authorize() -> None:
    manager = ApprovalManager()
    call = make_call()
    request = manager.create_pending(call, make_decision())

    assert manager.deny(request.approval_id)
    assert not manager.authorize(request.approval_id, call)
    assert not manager.authorize("missing", call)

    another = manager.create_pending(call, make_decision())
    assert manager.approve(another.approval_id)
    assert not manager.authorize(another.approval_id, make_call("CALL-2"))
    assert manager.get_approval(another.approval_id).status == ApprovalStatus.APPROVED


def test_expired_approval_cannot_be_approved_or_authorized() -> None:
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    manager = ApprovalManager(clock=lambda: now)
    call = make_call()
    request = manager.create_pending(
        call,
        make_decision(),
        expires_at=now + timedelta(seconds=1),
    )
    expired_at = now + timedelta(seconds=1)

    assert not manager.approve(request.approval_id, now=expired_at)
    assert request.status == ApprovalStatus.EXPIRED
    assert not manager.authorize(request.approval_id, call, now=expired_at)


def test_approval_requires_policy_decision_for_same_call() -> None:
    manager = ApprovalManager()
    call = make_call()

    with pytest.raises(ValueError, match="REQUIRE_APPROVAL"):
        manager.create_pending(
            call,
            PolicyDecision(
                decision_id="DEC-2",
                call_id=call.call_id,
                action=DecisionAction.ALLOW,
                reason="Allowed without approval.",
            ),
        )

    with pytest.raises(ValueError, match="refer to the supplied tool call"):
        manager.create_pending(call, make_decision("CALL-2"))


def test_approval_records_are_shared_through_injected_store() -> None:
    store = InMemoryStore()
    manager = ApprovalManager(store)
    request = manager.create_pending(make_call(), make_decision())

    assert store.approvals[request.approval_id] is request