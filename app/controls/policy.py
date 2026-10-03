from uuid import uuid4

from app.config import EXTERNAL_DESTINATION, SENSITIVE_LABELS
from app.contracts import DecisionAction, Guardrail, PolicyDecision, RiskLevel, ToolCall


class PolicyEngine:
    def __init__(self, guardrails: list[Guardrail] | None = None) -> None:
        self._guardrails = list(guardrails or [])

    @property
    def guardrails(self) -> list[Guardrail]:
        return list(self._guardrails)

    def install(self, guardrail: Guardrail) -> None:
        self._guardrails = [g for g in self._guardrails if g.guardrail_id != guardrail.guardrail_id]
        self._guardrails.append(guardrail)

    def evaluate(self, call: ToolCall, labels: set[str], destination: str | None) -> PolicyDecision:
        for guardrail in self._guardrails:
            if not guardrail.enabled:
                continue
            if labels.intersection(guardrail.source_labels) and destination == guardrail.destination:
                return PolicyDecision(
                    decision_id=f"DEC-{uuid4().hex[:8]}",
                    call_id=call.call_id,
                    action=guardrail.action,
                    reason=guardrail.reason,
                    matched_guardrail_id=guardrail.guardrail_id,
                    risk_level=RiskLevel.CRITICAL,
                )

        risky_external = bool(labels.intersection(SENSITIVE_LABELS)) and destination == EXTERNAL_DESTINATION
        return PolicyDecision(
            decision_id=f"DEC-{uuid4().hex[:8]}",
            call_id=call.call_id,
            action=DecisionAction.ALLOW,
            reason=(
                "No active guardrail matched; sensitive external flow is observable for attack discovery."
                if risky_external
                else "No active guardrail matched."
            ),
            risk_level=RiskLevel.HIGH if risky_external else RiskLevel.LOW,
        )
