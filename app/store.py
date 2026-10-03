"""In-memory persistence for runtime and security records."""

from typing import Any

from app.contracts import AttackPath, EffectReceipt, Guardrail, PolicyDecision


class InMemoryStore:
    """A process-local store whose data is isolated per instance."""

    def __init__(self) -> None:
        self.sessions: dict[str, dict[str, Any]] = {}
        self.receipts: dict[str, EffectReceipt] = {}
        self.decisions: dict[str, PolicyDecision] = {}
        self.guardrails: dict[str, Guardrail] = {}
        self.attack_runs: dict[str, AttackPath] = {}
        self.approvals: dict[str, Any] = {}

    def save_receipt(self, receipt: EffectReceipt) -> None:
        self.receipts[receipt.receipt_id] = receipt

    def get_receipt(self, receipt_id: str) -> EffectReceipt | None:
        return self.receipts.get(receipt_id)

    def list_receipts(self) -> list[EffectReceipt]:
        return list(self.receipts.values())

    def save_decision(self, decision: PolicyDecision) -> None:
        self.decisions[decision.decision_id] = decision

    def get_decision(self, decision_id: str) -> PolicyDecision | None:
        return self.decisions.get(decision_id)

    def list_decisions(self) -> list[PolicyDecision]:
        return list(self.decisions.values())

    def save_guardrail(self, guardrail: Guardrail) -> None:
        self.guardrails[guardrail.guardrail_id] = guardrail

    def get_guardrail(self, guardrail_id: str) -> Guardrail | None:
        return self.guardrails.get(guardrail_id)

    def list_guardrails(self) -> list[Guardrail]:
        return list(self.guardrails.values())

    def create_session(
        self, session_id: str, session: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        created_session = dict(session or {})
        created_session.setdefault("session_id", session_id)
        self.sessions[session_id] = created_session
        return created_session

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        return self.sessions.get(session_id)

    def reset(self) -> None:
        self.sessions.clear()
        self.receipts.clear()
        self.decisions.clear()
        self.guardrails.clear()
        self.attack_runs.clear()
        self.approvals.clear()