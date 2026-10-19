
"""Verify that AegisTwin SQLite evidence survives online backup and restore."""

import sqlite3
from pathlib import Path

from app.contracts import (
    DecisionAction,
    EffectReceipt,
    Guardrail,
    InstructionOrigin,
    PolicyDecision,
    ToolCall,
)
from app.persistence.sqlite_store import SQLiteEvidenceStore


def sample_receipt():
    call = ToolCall(
        call_id="CALL-BACKUP-001",
        session_id="SESSION-BACKUP-001",
        tool_name="summarizer",
        arguments={"text": "Approved security report"},
        instruction_origin=InstructionOrigin.USER,
        original_user_intent="Summarize an approved report",
    )
    return EffectReceipt(
        receipt_id="RCP-BACKUP-001",
        call=call,
        succeeded=True,
    )


def sample_decision():
    return PolicyDecision(
        decision_id="DEC-BACKUP-001",
        call_id="CALL-BACKUP-001",
        action=DecisionAction.BLOCK,
        reason="Blocked by a synthetic backup test policy",
    )


def sample_guardrail():
    return Guardrail(
        guardrail_id="GR-BACKUP-001",
        source_labels={"CustomerPII"},
        destination="EXTERNAL",
        action=DecisionAction.BLOCK,
        generated_from_attack="ATTACK-BACKUP-001",
        reason="Prevent external exposure of sensitive data",
    )


def backup_sqlite(source: Path, destination: Path) -> None:
    """Use the SQLite Online Backup API instead of copying the DB file."""
    if source.resolve() == destination.resolve():
        raise ValueError("Backup destination cannot equal source")

    destination.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(
        f"file:{source}?mode=ro",
        uri=True,
    ) as original:
        with sqlite3.connect(destination) as backup:
            original.backup(backup)

    with sqlite3.connect(destination) as connection:
        status = connection.execute("PRAGMA integrity_check").fetchone()
        assert status == ("ok",)


def test_sqlite_evidence_recovers_from_online_backup(tmp_path: Path) -> None:
    source_path = tmp_path / "live" / "aegistwin-runtime.db"
    backup_path = tmp_path / "backups" / "snapshot.db"
    restored_path = tmp_path / "restore" / "restored-runtime.db"

    source_path.parent.mkdir(parents=True)

    source = SQLiteEvidenceStore(source_path)

    receipt = sample_receipt()
    decision = sample_decision()
    guardrail = sample_guardrail()

    try:
        source.create_session(
            "SESSION-BACKUP-001",
            {"status": "active", "owner": "security-team"},
        )
        source.save_receipt(receipt)
        source.save_decision(
            decision,
            session_id="SESSION-BACKUP-001",
        )
        source.save_guardrail(guardrail)

        before = source.session_snapshot("SESSION-BACKUP-001")
        assert before["receipt_count"] == 1
        assert before["decision_count"] == 1

        # Keep the SQLiteEvidenceStore open while backing up.
        backup_sqlite(source_path, backup_path)

        # A restore into a new file must work independently of
        # the original SQLite database and its WAL files.
        restored_path.parent.mkdir(parents=True)
        with sqlite3.connect(backup_path) as snapshot:
            with sqlite3.connect(restored_path) as target:
                snapshot.backup(target)

        restored = SQLiteEvidenceStore(restored_path)

        try:
            assert restored.get_receipt(receipt.receipt_id) == receipt
            assert restored.get_decision(decision.decision_id) == decision
            assert restored.get_guardrail(guardrail.guardrail_id) == guardrail

            session = restored.get_session("SESSION-BACKUP-001")
            assert session is not None
            assert session["owner"] == "security-team"
            assert session["status"] == "active"

            after = restored.session_snapshot("SESSION-BACKUP-001")
            assert after["receipt_count"] == before["receipt_count"]
            assert after["decision_count"] == before["decision_count"]
        finally:
            restored.close()
    finally:
        source.close()
