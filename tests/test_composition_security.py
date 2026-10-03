from collections.abc import Awaitable, Callable

import pytest

from app.contracts import (
    DataArtifact,
    DecisionAction,
    EffectReceipt,
    InstructionOrigin,
    ToolCall,
)
from app.controls.policy import PolicyEngine
from app.gateway.service import Gateway
from app.security.composition import (
    SessionCompositionAnalyzer,
)
from app.security.semantic import (
    DeterministicFallbackDetector,
)
from app.store import InMemoryStore


def make_call(
    *,
    call_id: str,
    tool_name: str,
    intent: str,
    origin: InstructionOrigin,
    session_id: str = "SES-COMPOSITION-1",
    arguments: dict | None = None,
) -> ToolCall:
    return ToolCall(
        call_id=call_id,
        session_id=session_id,
        tool_name=tool_name,
        arguments=arguments or {},
        instruction_origin=origin,
        original_user_intent=intent,
    )


def make_receipt(
    *,
    receipt_id: str,
    call: ToolCall,
    labels: set[str] | None = None,
) -> EffectReceipt:
    artifact = DataArtifact(
        artifact_id=f"ART-{receipt_id}",
        value="protected customer information",
        labels=labels or set(),
    )

    return EffectReceipt(
        receipt_id=receipt_id,
        call=call,
        output_artifacts=[artifact],
        succeeded=True,
    )


def fake_executor_for(
    executed: list[ToolCall],
) -> Callable[
    [ToolCall, list[DataArtifact]],
    Awaitable[EffectReceipt],
]:
    async def fake_executor(
        call: ToolCall,
        inputs: list[DataArtifact],
    ) -> EffectReceipt:
        executed.append(call)

        return EffectReceipt(
            receipt_id=f"REC-{call.call_id}",
            call=call,
            input_artifact_ids=[
                artifact.artifact_id
                for artifact in inputs
            ],
            succeeded=True,
        )

    return fake_executor


def test_detects_compositional_data_exfiltration() -> None:
    analyzer = SessionCompositionAnalyzer()

    intent = "Summarize the customer invoice internally."

    database_call = make_call(
        call_id="CALL-DATABASE",
        tool_name="customer_database",
        intent=intent,
        origin=InstructionOrigin.DOCUMENT_UNTRUSTED,
    )

    summary_call = make_call(
        call_id="CALL-SUMMARY",
        tool_name="summarizer",
        intent=intent,
        origin=InstructionOrigin.DOCUMENT_UNTRUSTED,
    )

    external_call = make_call(
        call_id="CALL-EXTERNAL",
        tool_name="external_http",
        intent=intent,
        origin=InstructionOrigin.DOCUMENT_UNTRUSTED,
    )

    receipts = [
        make_receipt(
            receipt_id="REC-DATABASE",
            call=database_call,
            labels={"CustomerPII"},
        ),
        make_receipt(
            receipt_id="REC-SUMMARY",
            call=summary_call,
            labels={"DerivedFrom<CustomerPII>"},
        ),
    ]

    verdict = analyzer.analyze(
        receipts=receipts,
        proposed_call=external_call,
        input_artifacts=[
            DataArtifact(
                artifact_id="ART-SUMMARY",
                value="derived confidential summary",
                labels={"DerivedFrom<CustomerPII>"},
            )
        ],
    )

    assert verdict.dangerous
    assert (
        verdict.category
        == "COMPOSITIONAL_DATA_EXFILTRATION"
    )
    assert verdict.score == 0.99
    assert verdict.tool_sequence == [
        "customer_database",
        "summarizer",
        "external_http",
    ]


def test_allows_explicitly_authorized_external_transfer() -> None:
    analyzer = SessionCompositionAnalyzer()

    intent = (
        "Send the approved report to "
        "partner@example.com."
    )

    external_call = make_call(
        call_id="CALL-AUTHORIZED",
        tool_name="external_http",
        intent=intent,
        origin=InstructionOrigin.USER,
    )

    verdict = analyzer.analyze(
        receipts=[],
        proposed_call=external_call,
        input_artifacts=[
            DataArtifact(
                artifact_id="ART-APPROVED",
                value="approved report",
                labels={"CustomerPII"},
            )
        ],
    )

    assert not verdict.dangerous
    assert verdict.category == "BENIGN_COMPOSITION"


@pytest.mark.asyncio
async def test_gateway_blocks_dangerous_session_chain() -> None:
    store = InMemoryStore()
    executed: list[ToolCall] = []
    intent = "Summarize the customer invoice internally."

    historical_call = make_call(
        call_id="CALL-HISTORICAL",
        tool_name="customer_database",
        intent=intent,
        origin=InstructionOrigin.DOCUMENT_UNTRUSTED,
    )

    store.save_receipt(
        make_receipt(
            receipt_id="REC-HISTORICAL",
            call=historical_call,
            labels={"CustomerPII"},
        )
    )

    gateway = Gateway(
        PolicyEngine(),
        store=store,
        semantic_detector=(
            DeterministicFallbackDetector()
        ),
        enforce_composition=True,
        executor=fake_executor_for(executed),
    )

    proposed_call = make_call(
        call_id="CALL-PROPOSED",
        tool_name="external_http",
        intent=intent,
        origin=InstructionOrigin.DOCUMENT_UNTRUSTED,
    )

    decision, receipt = await gateway.process(
        proposed_call,
        [
            DataArtifact(
                artifact_id="ART-DERIVED",
                value="customer summary",
                labels={"DerivedFrom<CustomerPII>"},
            )
        ],
    )

    assert decision.action == DecisionAction.BLOCK
    assert "Session composition control blocked" in (
        decision.reason
    )
    assert "COMPOSITIONAL_DATA_EXFILTRATION" in (
        decision.reason
    )
    assert receipt is None
    assert executed == []


def test_store_builds_accumulated_session_snapshot() -> None:
    store = InMemoryStore()

    call = make_call(
        call_id="CALL-SNAPSHOT",
        tool_name="customer_database",
        intent="Read the approved customer record.",
        origin=InstructionOrigin.USER,
    )

    receipt = make_receipt(
        receipt_id="REC-SNAPSHOT",
        call=call,
        labels={"CustomerPII"},
    )

    store.save_receipt(receipt)

    snapshot = store.session_snapshot(
        call.session_id
    )

    assert snapshot["receipt_count"] == 1
    assert snapshot["tool_sequence"] == [
        "customer_database"
    ]
    assert snapshot["data_labels"] == [
        "CustomerPII"
    ]
    assert snapshot["receipt_ids"] == [
        "REC-SNAPSHOT"
    ]