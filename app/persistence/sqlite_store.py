"""SQLite-backed evidence store layered on top of InMemoryStore.

The existing in-memory behavior remains the primary runtime interface.
This adapter mirrors important evidence to SQLite and restores it when a
new process starts.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from threading import RLock
from typing import Any

from pydantic import BaseModel

from app.contracts import (
    EffectReceipt,
    Guardrail,
    PolicyDecision,
)
from app.store import InMemoryStore


DEFAULT_SQLITE_PATH = (
    Path("data")
    / "aegistwin-runtime.db"
)


def _json_safe(
    value: Any,
) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(
            mode="json"
        )

    if isinstance(value, Enum):
        return value.value

    if isinstance(value, datetime):
        return value.isoformat()

    if isinstance(value, dict):
        return {
            str(key): _json_safe(
                nested_value
            )
            for key, nested_value
            in value.items()
        }

    if isinstance(value, (list, tuple)):
        return [
            _json_safe(item)
            for item in value
        ]

    if isinstance(value, set):
        return sorted(
            _json_safe(item)
            for item in value
        )

    return value


def _dumps(
    value: Any,
) -> str:
    return json.dumps(
        _json_safe(value),
        sort_keys=True,
        separators=(",", ":"),
    )


def _loads(
    value: str,
) -> Any:
    return json.loads(value)


class SQLiteEvidenceStore(
    InMemoryStore
):
    """In-memory store mirrored durably to SQLite."""

    def __init__(
        self,
        path: str | Path = DEFAULT_SQLITE_PATH,
    ) -> None:
        super().__init__()

        self.path = Path(path)

        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._db_lock = RLock()

        self._connection = sqlite3.connect(
            self.path,
            check_same_thread=False,
        )

        self._connection.execute(
            "PRAGMA journal_mode=WAL"
        )

        self._connection.execute(
            "PRAGMA foreign_keys=ON"
        )

        self._initialize_schema()
        self._restore_from_sqlite()

    def _initialize_schema(
        self,
    ) -> None:
        with self._db_lock:
            self._connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS receipts (
                    receipt_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    call_id TEXT NOT NULL,
                    tool_name TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS
                idx_receipts_session_id
                ON receipts(session_id);

                CREATE TABLE IF NOT EXISTS decisions (
                    decision_id TEXT PRIMARY KEY,
                    session_id TEXT,
                    call_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    risk_level TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS
                idx_decisions_session_id
                ON decisions(session_id);

                CREATE TABLE IF NOT EXISTS guardrails (
                    guardrail_id TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )

            self._connection.commit()

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(
            timezone.utc
        ).isoformat()

    def _restore_from_sqlite(
        self,
    ) -> None:
        with self._db_lock:
            session_rows = (
                self._connection.execute(
                    """
                    SELECT
                        session_id,
                        payload_json
                    FROM sessions
                    ORDER BY rowid
                    """
                ).fetchall()
            )

            receipt_rows = (
                self._connection.execute(
                    """
                    SELECT payload_json
                    FROM receipts
                    ORDER BY rowid
                    """
                ).fetchall()
            )

            decision_rows = (
                self._connection.execute(
                    """
                    SELECT
                        session_id,
                        payload_json
                    FROM decisions
                    ORDER BY rowid
                    """
                ).fetchall()
            )

            guardrail_rows = (
                self._connection.execute(
                    """
                    SELECT payload_json
                    FROM guardrails
                    ORDER BY rowid
                    """
                ).fetchall()
            )

        for session_id, payload_json in session_rows:
            payload = _loads(
                payload_json
            )

            if not isinstance(payload, dict):
                continue

            payload.setdefault(
                "session_id",
                session_id,
            )

            self.sessions[
                session_id
            ] = payload

        for (payload_json,) in receipt_rows:
            receipt = (
                EffectReceipt.model_validate(
                    _loads(
                        payload_json
                    )
                )
            )

            self.receipts[
                receipt.receipt_id
            ] = receipt

            session = (
                self.sessions.setdefault(
                    receipt.call.session_id,
                    {
                        "session_id": (
                            receipt.call.session_id
                        )
                    },
                )
            )

            receipt_ids = (
                session.setdefault(
                    "receipt_ids",
                    [],
                )
            )

            if (
                receipt.receipt_id
                not in receipt_ids
            ):
                receipt_ids.append(
                    receipt.receipt_id
                )

        for session_id, payload_json in decision_rows:
            decision = (
                PolicyDecision.model_validate(
                    _loads(
                        payload_json
                    )
                )
            )

            self.decisions[
                decision.decision_id
            ] = decision

            if session_id is not None:
                session = (
                    self.sessions.setdefault(
                        session_id,
                        {
                            "session_id": (
                                session_id
                            )
                        },
                    )
                )

                decision_ids = (
                    session.setdefault(
                        "decision_ids",
                        [],
                    )
                )

                if (
                    decision.decision_id
                    not in decision_ids
                ):
                    decision_ids.append(
                        decision.decision_id
                    )

        for (payload_json,) in guardrail_rows:
            guardrail = (
                Guardrail.model_validate(
                    _loads(
                        payload_json
                    )
                )
            )

            self.guardrails[
                guardrail.guardrail_id
            ] = guardrail

    def _persist_session(
        self,
        session_id: str,
    ) -> None:
        session = self.sessions.get(
            session_id
        )

        if session is None:
            return

        with self._db_lock:
            self._connection.execute(
                """
                INSERT INTO sessions (
                    session_id,
                    payload_json,
                    updated_at
                )
                VALUES (?, ?, ?)
                ON CONFLICT(session_id)
                DO UPDATE SET
                    payload_json = excluded.payload_json,
                    updated_at = excluded.updated_at
                """,
                (
                    session_id,
                    _dumps(session),
                    self._utc_now(),
                ),
            )

            self._connection.commit()

    def create_session(
        self,
        session_id: str,
        session: dict[
            str,
            Any,
        ] | None = None,
    ) -> dict[
        str,
        Any,
    ]:
        created = super().create_session(
            session_id,
            session,
        )

        self._persist_session(
            session_id
        )

        return created

    def save_receipt(
        self,
        receipt: EffectReceipt,
    ) -> None:
        super().save_receipt(
            receipt
        )

        with self._db_lock:
            self._connection.execute(
                """
                INSERT INTO receipts (
                    receipt_id,
                    session_id,
                    call_id,
                    tool_name,
                    payload_json,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(receipt_id)
                DO UPDATE SET
                    session_id = excluded.session_id,
                    call_id = excluded.call_id,
                    tool_name = excluded.tool_name,
                    payload_json = excluded.payload_json
                """,
                (
                    receipt.receipt_id,
                    receipt.call.session_id,
                    receipt.call.call_id,
                    receipt.call.tool_name,
                    _dumps(receipt),
                    self._utc_now(),
                ),
            )

            self._connection.commit()

        self._persist_session(
            receipt.call.session_id
        )

    def save_decision(
        self,
        decision: PolicyDecision,
        session_id: str | None = None,
    ) -> None:
        super().save_decision(
            decision,
            session_id=session_id,
        )

        with self._db_lock:
            self._connection.execute(
                """
                INSERT INTO decisions (
                    decision_id,
                    session_id,
                    call_id,
                    action,
                    risk_level,
                    payload_json,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(decision_id)
                DO UPDATE SET
                    session_id = excluded.session_id,
                    call_id = excluded.call_id,
                    action = excluded.action,
                    risk_level = excluded.risk_level,
                    payload_json = excluded.payload_json
                """,
                (
                    decision.decision_id,
                    session_id,
                    decision.call_id,
                    decision.action.value,
                    decision.risk_level.value,
                    _dumps(decision),
                    self._utc_now(),
                ),
            )

            self._connection.commit()

        if session_id is not None:
            self._persist_session(
                session_id
            )

    def save_guardrail(
        self,
        guardrail: Guardrail,
    ) -> None:
        super().save_guardrail(
            guardrail
        )

        with self._db_lock:
            self._connection.execute(
                """
                INSERT INTO guardrails (
                    guardrail_id,
                    payload_json,
                    updated_at
                )
                VALUES (?, ?, ?)
                ON CONFLICT(guardrail_id)
                DO UPDATE SET
                    payload_json = excluded.payload_json,
                    updated_at = excluded.updated_at
                """,
                (
                    guardrail.guardrail_id,
                    _dumps(guardrail),
                    self._utc_now(),
                ),
            )

            self._connection.commit()

    def persistence_status(
        self,
    ) -> dict[
        str,
        Any,
    ]:
        with self._db_lock:
            session_count = (
                self._connection.execute(
                    "SELECT COUNT(*) FROM sessions"
                ).fetchone()[0]
            )

            receipt_count = (
                self._connection.execute(
                    "SELECT COUNT(*) FROM receipts"
                ).fetchone()[0]
            )

            decision_count = (
                self._connection.execute(
                    "SELECT COUNT(*) FROM decisions"
                ).fetchone()[0]
            )

            guardrail_count = (
                self._connection.execute(
                    "SELECT COUNT(*) FROM guardrails"
                ).fetchone()[0]
            )

        return {
            "backend": "sqlite",
            "path": str(
                self.path
            ),
            "sessions": session_count,
            "receipts": receipt_count,
            "decisions": decision_count,
            "guardrails": guardrail_count,
        }

    def reset(
        self,
    ) -> None:
        super().reset()

        with self._db_lock:
            self._connection.executescript(
                """
                DELETE FROM sessions;
                DELETE FROM receipts;
                DELETE FROM decisions;
                DELETE FROM guardrails;
                """
            )

            self._connection.commit()

    def close(
        self,
    ) -> None:
        with self._db_lock:
            self._connection.close()