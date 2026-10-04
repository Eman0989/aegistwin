"""Judge-friendly runtime audit events and export helpers.

This module supplements the existing InMemoryStore. It does not replace
decisions, receipts, telemetry, approvals, or session evidence.
"""

from __future__ import annotations

import csv
import io
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from threading import Lock
from typing import Any

from app.contracts import DecisionAction, RiskLevel


@dataclass(frozen=True)
class AuditEvent:
    """One gateway evaluation represented as exportable audit evidence."""

    timestamp: datetime
    session_id: str
    call_id: str
    tool_name: str
    instruction_origin: str
    control: str
    action: str
    reason: str
    risk: str
    latency_ms: float
    executed: bool
    decision_id: str
    receipt_id: str | None
    policy_version: str

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["timestamp"] = self.timestamp.isoformat()
        return payload


def infer_control(
    *,
    reason: str,
    action: DecisionAction,
    executed: bool,
) -> str:
    """Infer which existing control produced a gateway decision."""

    normalized = reason.lower()

    if "unsupported tool" in normalized:
        return "tool_allow_list"

    if "semantic control" in normalized:
        return "semantic_detection"

    if "session composition control" in normalized:
        return "session_composition"

    if (
        "approval" in normalized
        or action == DecisionAction.REQUIRE_APPROVAL
    ):
        return "human_approval"

    if (
        "cost" in normalized
        or "budget" in normalized
        or "tool call" in normalized
        or "external http" in normalized
    ):
        return "budget_control"

    # Important:
    # A successfully executed ALLOW is classified as execution
    # before checking generic words such as "guardrail".
    if (
        executed
        and action == DecisionAction.ALLOW
    ):
        return "execution"

    if (
        "policy" in normalized
        or "guardrail" in normalized
        or action in {
            DecisionAction.BLOCK,
            DecisionAction.REDACT,
        }
    ):
        return "deterministic_policy"

    return "gateway"


class AuditLog:
    """Thread-safe process-local audit event recorder."""

    def __init__(self) -> None:
        self._events: list[AuditEvent] = []
        self._lock = Lock()

    def record(
        self,
        *,
        session_id: str,
        call_id: str,
        tool_name: str,
        instruction_origin: str,
        action: DecisionAction,
        reason: str,
        risk: RiskLevel,
        latency_ms: float,
        executed: bool,
        decision_id: str,
        receipt_id: str | None,
        policy_version: str,
        control: str,
        timestamp: datetime | None = None,
    ) -> AuditEvent:
        if latency_ms < 0:
            raise ValueError(
                "latency_ms cannot be negative."
            )

        event = AuditEvent(
            timestamp=(
                timestamp
                or datetime.now(timezone.utc)
            ),
            session_id=session_id,
            call_id=call_id,
            tool_name=tool_name,
            instruction_origin=instruction_origin,
            control=control,
            action=action.value,
            reason=reason,
            risk=risk.value,
            latency_ms=float(latency_ms),
            executed=executed,
            decision_id=decision_id,
            receipt_id=receipt_id,
            policy_version=policy_version,
        )

        with self._lock:
            self._events.append(event)

        return event

    def list_events(self) -> list[AuditEvent]:
        with self._lock:
            return list(self._events)

    def list_event_dicts(
        self,
    ) -> list[dict[str, Any]]:
        return [
            event.as_dict()
            for event in self.list_events()
        ]

    def export_json(self) -> dict[str, Any]:
        events = self.list_event_dicts()

        return {
            "status": "ok",
            "format": "json",
            "event_count": len(events),
            "events": events,
        }

    def export_csv(self) -> str:
        fieldnames = [
            "timestamp",
            "session_id",
            "call_id",
            "tool_name",
            "instruction_origin",
            "control",
            "action",
            "reason",
            "risk",
            "latency_ms",
            "executed",
            "decision_id",
            "receipt_id",
            "policy_version",
        ]

        output = io.StringIO()

        writer = csv.DictWriter(
            output,
            fieldnames=fieldnames,
        )

        writer.writeheader()

        for event in self.list_event_dicts():
            writer.writerow(event)

        return output.getvalue()

    def reset(self) -> None:
        with self._lock:
            self._events.clear()