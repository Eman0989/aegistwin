from app.contracts import (
    AttackPath,
    DecisionAction,
    EffectReceipt,
    Guardrail,
    InstructionOrigin,
    PolicyDecision,
    RiskLevel,
    ToolCall,
)
from app.store import InMemoryStore


def make_receipt(receipt_id: str) -> EffectReceipt:
    call = ToolCall(
        call_id=f"CALL-{receipt_id}",
        session_id="SES-1",
        tool_name="invoice_reader",
        instruction_origin=InstructionOrigin.USER,
        original_user_intent="Read invoice",
    )
    return EffectReceipt(receipt_id=receipt_id, call=call, succeeded=True)


def make_decision(decision_id: str) -> PolicyDecision:
    return PolicyDecision(
        decision_id=decision_id,
        call_id="CALL-1",
        action=DecisionAction.ALLOW,
        reason="No active guardrail matched.",
    )


def make_guardrail(guardrail_id: str) -> Guardrail:
    return Guardrail(
        guardrail_id=guardrail_id,
        source_labels={"PII"},
        destination="EXTERNAL",
        generated_from_attack="ATTACK-1",
        reason="Block sensitive data leaving the system.",
    )


def test_store_saves_retrieves_and_lists_contract_records() -> None:
    store = InMemoryStore()
    receipt = make_receipt("REC-1")
    decision = make_decision("DEC-1")
    guardrail = make_guardrail("GR-1")

    store.save_receipt(receipt)
    store.save_decision(decision)
    store.save_guardrail(guardrail)

    assert store.get_receipt("REC-1") == receipt
    assert store.list_receipts() == [receipt]
    assert store.get_decision("DEC-1") == decision
    assert store.list_decisions() == [decision]
    assert store.get_guardrail("GR-1") == guardrail
    assert store.list_guardrails() == [guardrail]


def test_store_creates_and_retrieves_sessions() -> None:
    store = InMemoryStore()

    session = store.create_session("SES-1", {"status": "active"})

    assert session == {"session_id": "SES-1", "status": "active"}
    assert store.get_session("SES-1") == session
    assert store.get_session("missing") is None


def test_reset_clears_all_store_collections() -> None:
    store = InMemoryStore()
    store.create_session("SES-1")
    store.save_receipt(make_receipt("REC-1"))
    store.save_decision(make_decision("DEC-1"))
    store.save_guardrail(make_guardrail("GR-1"))
    store.attack_runs["ATTACK-1"] = AttackPath(
        attack_id="ATTACK-1",
        original_intent="Send invoice externally",
        instruction_origin=InstructionOrigin.WEB_UNTRUSTED,
        path=["invoice_reader", "external_http"],
        final_effect="External data transfer",
        risk_level=RiskLevel.CRITICAL,
    )
    store.approvals["APP-1"] = {"status": "pending"}

    store.reset()

    assert store.sessions == {}
    assert store.receipts == {}
    assert store.decisions == {}
    assert store.guardrails == {}
    assert store.attack_runs == {}
    assert store.approvals == {}


def test_store_instances_do_not_share_state() -> None:
    first_store = InMemoryStore()
    second_store = InMemoryStore()

    first_store.create_session("SES-1")

    assert second_store.sessions == {}