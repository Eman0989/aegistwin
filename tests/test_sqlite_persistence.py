from pathlib import Path

from app.contracts import (
    DecisionAction,
    EffectReceipt,
    Guardrail,
    InstructionOrigin,
    PolicyDecision,
    ToolCall,
)
from app.persistence.sqlite_store import (
    SQLiteEvidenceStore,
)


def _receipt() -> EffectReceipt:
    call = ToolCall(
        call_id="CALL-SQLITE-001",
        session_id="SESSION-SQLITE-001",
        tool_name="summarizer",
        arguments={
            "text": "Approved report."
        },
        instruction_origin=(
            InstructionOrigin.USER
        ),
        original_user_intent=(
            "Summarize approved report."
        ),
    )

    return EffectReceipt(
        receipt_id="RCP-SQLITE-001",
        call=call,
        succeeded=True,
    )


def _decision() -> PolicyDecision:
    return PolicyDecision(
        decision_id="DEC-SQLITE-001",
        call_id="CALL-SQLITE-001",
        action=DecisionAction.ALLOW,
        reason=(
            "No active guardrail matched."
        ),
    )


def _guardrail() -> Guardrail:
    return Guardrail(
        guardrail_id="GR-SQLITE-001",
        source_labels={
            "CustomerPII"
        },
        destination="EXTERNAL",
        action=DecisionAction.BLOCK,
        generated_from_attack=(
            "ATTACK-SQLITE-001"
        ),
        reason=(
            "Block sensitive external data."
        ),
    )


def test_sqlite_store_persists_receipt_and_decision(
    tmp_path: Path,
) -> None:
    database = (
        tmp_path
        / "runtime.db"
    )

    store = SQLiteEvidenceStore(
        database
    )

    receipt = _receipt()
    decision = _decision()

    store.save_receipt(
        receipt
    )

    store.save_decision(
        decision,
        session_id=(
            "SESSION-SQLITE-001"
        ),
    )

    status = (
        store.persistence_status()
    )

    assert (
        status["sessions"]
        == 1
    )

    assert (
        status["receipts"]
        == 1
    )

    assert (
        status["decisions"]
        == 1
    )

    store.close()


def test_new_store_restores_evidence_from_same_database(
    tmp_path: Path,
) -> None:
    database = (
        tmp_path
        / "restore.db"
    )

    first = SQLiteEvidenceStore(
        database
    )

    first.save_receipt(
        _receipt()
    )

    first.save_decision(
        _decision(),
        session_id=(
            "SESSION-SQLITE-001"
        ),
    )

    first.save_guardrail(
        _guardrail()
    )

    first.close()

    second = SQLiteEvidenceStore(
        database
    )

    restored_receipt = (
        second.get_receipt(
            "RCP-SQLITE-001"
        )
    )

    restored_decision = (
        second.get_decision(
            "DEC-SQLITE-001"
        )
    )

    restored_guardrail = (
        second.get_guardrail(
            "GR-SQLITE-001"
        )
    )

    assert (
        restored_receipt
        is not None
    )

    assert (
        restored_receipt
        .call
        .session_id
        == "SESSION-SQLITE-001"
    )

    assert (
        restored_decision
        == _decision()
    )

    assert (
        restored_guardrail
        == _guardrail()
    )

    snapshot = (
        second.session_snapshot(
            "SESSION-SQLITE-001"
        )
    )

    assert (
        snapshot["receipt_count"]
        == 1
    )

    assert (
        snapshot["decision_count"]
        == 1
    )

    second.close()


def test_sqlite_store_preserves_session_metadata(
    tmp_path: Path,
) -> None:
    database = (
        tmp_path
        / "metadata.db"
    )

    first = SQLiteEvidenceStore(
        database
    )

    first.create_session(
        "SESSION-META-001",
        {
            "status": "active",
            "owner": "security-team",
        },
    )

    first.save_decision(
        PolicyDecision(
            decision_id=(
                "DEC-META-001"
            ),
            call_id=(
                "CALL-META-001"
            ),
            action=(
                DecisionAction.BLOCK
            ),
            reason=(
                "Test policy block."
            ),
        ),
        session_id=(
            "SESSION-META-001"
        ),
    )

    first.close()

    second = SQLiteEvidenceStore(
        database
    )

    session = (
        second.get_session(
            "SESSION-META-001"
        )
    )

    assert (
        session is not None
    )

    assert (
        session["status"]
        == "active"
    )

    assert (
        session["owner"]
        == "security-team"
    )

    assert (
        "DEC-META-001"
        in session[
            "decision_ids"
        ]
    )

    second.close()


def test_sqlite_store_persists_guardrail(
    tmp_path: Path,
) -> None:
    database = (
        tmp_path
        / "guardrail.db"
    )

    store = SQLiteEvidenceStore(
        database
    )

    store.save_guardrail(
        _guardrail()
    )

    status = (
        store.persistence_status()
    )

    assert (
        status["guardrails"]
        == 1
    )

    assert (
        store.get_guardrail(
            "GR-SQLITE-001"
        )
        == _guardrail()
    )

    store.close()


def test_sqlite_reset_clears_memory_and_database(
    tmp_path: Path,
) -> None:
    database = (
        tmp_path
        / "reset.db"
    )

    store = SQLiteEvidenceStore(
        database
    )

    store.save_receipt(
        _receipt()
    )

    store.save_decision(
        _decision(),
        session_id=(
            "SESSION-SQLITE-001"
        ),
    )

    store.save_guardrail(
        _guardrail()
    )

    store.reset()

    assert (
        store.sessions
        == {}
    )

    assert (
        store.receipts
        == {}
    )

    assert (
        store.decisions
        == {}
    )

    assert (
        store.guardrails
        == {}
    )

    status = (
        store.persistence_status()
    )

    assert (
        status["sessions"]
        == 0
    )

    assert (
        status["receipts"]
        == 0
    )

    assert (
        status["decisions"]
        == 0
    )

    assert (
        status["guardrails"]
        == 0
    )

    store.close()


def test_persistence_status_reports_sqlite_backend(
    tmp_path: Path,
) -> None:
    database = (
        tmp_path
        / "status.db"
    )

    store = SQLiteEvidenceStore(
        database
    )

    status = (
        store.persistence_status()
    )

    assert (
        status["backend"]
        == "sqlite"
    )

    assert (
        status["path"]
        == str(database)
    )

    assert (
        status["sessions"]
        == 0
    )

    assert (
        status["receipts"]
        == 0
    )

    assert (
        status["decisions"]
        == 0
    )

    assert (
        status["guardrails"]
        == 0
    )

    store.close()