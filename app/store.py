"""In-memory persistence for runtime and security records."""

from typing import Any

from app.contracts import (
    AttackPath,
    EffectReceipt,
    Guardrail,
    PolicyDecision,
)


class InMemoryStore:
    """Process-local storage for runtime and security evidence."""

    def __init__(self) -> None:
        self.sessions: dict[str, dict[str, Any]] = {}
        self.receipts: dict[str, EffectReceipt] = {}
        self.decisions: dict[str, PolicyDecision] = {}
        self.guardrails: dict[str, Guardrail] = {}
        self.attack_runs: dict[str, AttackPath] = {}
        self.approvals: dict[str, Any] = {}

    def save_receipt(
        self,
        receipt: EffectReceipt,
    ) -> None:
        self.receipts[receipt.receipt_id] = receipt

        session = self.sessions.setdefault(
            receipt.call.session_id,
            {
                "session_id": receipt.call.session_id,
            },
        )

        receipt_ids = session.setdefault(
            "receipt_ids",
            [],
        )

        if receipt.receipt_id not in receipt_ids:
            receipt_ids.append(receipt.receipt_id)

    def get_receipt(
        self,
        receipt_id: str,
    ) -> EffectReceipt | None:
        return self.receipts.get(receipt_id)

    def list_receipts(self) -> list[EffectReceipt]:
        return list(self.receipts.values())

    def list_receipts_for_session(
        self,
        session_id: str,
    ) -> list[EffectReceipt]:
        session = self.sessions.get(session_id, {})
        receipt_ids = session.get("receipt_ids", [])

        return [
            self.receipts[receipt_id]
            for receipt_id in receipt_ids
            if receipt_id in self.receipts
        ]

    def save_decision(
        self,
        decision: PolicyDecision,
        session_id: str | None = None,
    ) -> None:
        self.decisions[decision.decision_id] = decision

        if session_id is None:
            return

        session = self.sessions.setdefault(
            session_id,
            {
                "session_id": session_id,
            },
        )

        decision_ids = session.setdefault(
            "decision_ids",
            [],
        )

        if decision.decision_id not in decision_ids:
            decision_ids.append(decision.decision_id)

    def get_decision(
        self,
        decision_id: str,
    ) -> PolicyDecision | None:
        return self.decisions.get(decision_id)

    def list_decisions(self) -> list[PolicyDecision]:
        return list(self.decisions.values())

    def list_decisions_for_session(
        self,
        session_id: str,
    ) -> list[PolicyDecision]:
        session = self.sessions.get(session_id, {})
        decision_ids = session.get("decision_ids", [])

        return [
            self.decisions[decision_id]
            for decision_id in decision_ids
            if decision_id in self.decisions
        ]

    def save_guardrail(
        self,
        guardrail: Guardrail,
    ) -> None:
        self.guardrails[guardrail.guardrail_id] = guardrail

    def get_guardrail(
        self,
        guardrail_id: str,
    ) -> Guardrail | None:
        return self.guardrails.get(guardrail_id)

    def list_guardrails(self) -> list[Guardrail]:
        return list(self.guardrails.values())

    def create_session(
        self,
        session_id: str,
        session: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        created_session = dict(session or {})
        created_session.setdefault(
            "session_id",
            session_id,
        )

        self.sessions[session_id] = created_session

        return created_session

    def get_session(
        self,
        session_id: str,
    ) -> dict[str, Any] | None:
        return self.sessions.get(session_id)

    def session_snapshot(
        self,
        session_id: str,
    ) -> dict[str, Any]:
        session = self.sessions.get(
            session_id,
            {
                "session_id": session_id,
            },
        )

        receipts = self.list_receipts_for_session(
            session_id
        )
        decisions = self.list_decisions_for_session(
            session_id
        )

        data_labels = {
            label
            for receipt in receipts
            for artifact in receipt.output_artifacts
            for label in artifact.labels
        }

        return {
            "session_id": session_id,
            "receipt_count": len(receipts),
            "decision_count": len(decisions),
            "tool_sequence": [
                receipt.call.tool_name
                for receipt in receipts
            ],
            "instruction_origins": [
                receipt.call.instruction_origin.value
                for receipt in receipts
            ],
            "data_labels": sorted(data_labels),
            "receipt_ids": [
                receipt.receipt_id
                for receipt in receipts
            ],
            "decision_ids": [
                decision.decision_id
                for decision in decisions
            ],
            "metadata": {
                key: value
                for key, value in session.items()
                if key not in {
                    "session_id",
                    "receipt_ids",
                    "decision_ids",
                }
            },
        }

    def reset(self) -> None:
        self.sessions.clear()
        self.receipts.clear()
        self.decisions.clear()
        self.guardrails.clear()
        self.attack_runs.clear()
        self.approvals.clear()