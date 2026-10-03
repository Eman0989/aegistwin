"""Session-level detection of dangerous multi-tool compositions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.config import SENSITIVE_LABELS
from app.contracts import (
    DataArtifact,
    EffectReceipt,
    InstructionOrigin,
    RiskLevel,
    ToolCall,
)
from app.twin.intent_action import is_action_aligned


UNTRUSTED_ORIGINS = {
    InstructionOrigin.WEB_UNTRUSTED,
    InstructionOrigin.DOCUMENT_UNTRUSTED,
    InstructionOrigin.EMAIL_UNTRUSTED,
    InstructionOrigin.MCP_TOOL_OUTPUT,
    InstructionOrigin.EXTERNAL_API,
}

EXTERNAL_TOOLS = {
    "external_http",
    "send_email",
    "external_upload",
    "webhook",
}

SENSITIVE_ACCESS_TOOLS = {
    "customer_database",
    "invoice_reader",
    "secrets_manager",
    "file_reader",
}

TRANSFORMATION_TOOLS = {
    "summarizer",
    "translator",
    "document_processor",
    "llm",
}


@dataclass(frozen=True)
class CompositionVerdict:
    dangerous: bool
    score: float
    category: str
    reason: str
    risk_level: RiskLevel
    tool_sequence: list[str]
    evidence_receipt_ids: list[str]
    accumulated_labels: set[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "dangerous": self.dangerous,
            "score": round(self.score, 4),
            "category": self.category,
            "reason": self.reason,
            "risk_level": self.risk_level.value,
            "tool_sequence": self.tool_sequence,
            "evidence_receipt_ids": self.evidence_receipt_ids,
            "accumulated_labels": sorted(
                self.accumulated_labels
            ),
        }


class SessionCompositionAnalyzer:
    """Review accumulated receipts plus the proposed next action."""

    def analyze(
        self,
        *,
        receipts: list[EffectReceipt],
        proposed_call: ToolCall,
        input_artifacts: list[DataArtifact],
    ) -> CompositionVerdict:
        previous_tools = [
            receipt.call.tool_name
            for receipt in receipts
        ]

        tool_sequence = [
            *previous_tools,
            proposed_call.tool_name,
        ]

        evidence_receipt_ids = [
            receipt.receipt_id
            for receipt in receipts
        ]

        origins = [
            receipt.call.instruction_origin
            for receipt in receipts
        ]
        origins.append(
            proposed_call.instruction_origin
        )

        contains_untrusted_content = any(
            origin in UNTRUSTED_ORIGINS
            for origin in origins
        )

        historical_labels = {
            label
            for receipt in receipts
            for artifact in receipt.output_artifacts
            for label in artifact.labels
        }

        current_labels = {
            label
            for artifact in input_artifacts
            for label in artifact.labels
        }

        accumulated_labels = (
            historical_labels
            | current_labels
        )

        contains_sensitive_data = bool(
            accumulated_labels.intersection(
                SENSITIVE_LABELS
            )
        )

        accessed_sensitive_source = any(
            tool in SENSITIVE_ACCESS_TOOLS
            for tool in previous_tools
        )

        transformed_data = any(
            tool in TRANSFORMATION_TOOLS
            for tool in previous_tools
        )

        external_action = (
            proposed_call.tool_name
            in EXTERNAL_TOOLS
        )

        intent_allows_external_action = (
            is_action_aligned(
                proposed_call.original_user_intent,
                "EXTERNAL_TRANSFER",
            )
        )

        intent_mismatch = (
            external_action
            and not intent_allows_external_action
        )

        if (
            external_action
            and contains_sensitive_data
            and contains_untrusted_content
            and intent_mismatch
        ):
            return CompositionVerdict(
                dangerous=True,
                score=0.99,
                category=(
                    "COMPOSITIONAL_DATA_EXFILTRATION"
                ),
                reason=(
                    "The accumulated session combines "
                    "untrusted instructions, sensitive data "
                    "and an unauthorized external transfer."
                ),
                risk_level=RiskLevel.CRITICAL,
                tool_sequence=tool_sequence,
                evidence_receipt_ids=(
                    evidence_receipt_ids
                ),
                accumulated_labels=accumulated_labels,
            )

        if (
            external_action
            and contains_sensitive_data
            and intent_mismatch
        ):
            return CompositionVerdict(
                dangerous=True,
                score=0.96,
                category="INTENT_ACTION_MISMATCH",
                reason=(
                    "Sensitive data is being transferred "
                    "externally without explicit authorization "
                    "in the original user intent."
                ),
                risk_level=RiskLevel.CRITICAL,
                tool_sequence=tool_sequence,
                evidence_receipt_ids=(
                    evidence_receipt_ids
                ),
                accumulated_labels=accumulated_labels,
            )

        if (
            external_action
            and accessed_sensitive_source
            and transformed_data
            and intent_mismatch
        ):
            return CompositionVerdict(
                dangerous=True,
                score=0.93,
                category="DANGEROUS_TOOL_COMPOSITION",
                reason=(
                    "A sensitive data source and transformation "
                    "tool are being composed with an unauthorized "
                    "external sink."
                ),
                risk_level=RiskLevel.CRITICAL,
                tool_sequence=tool_sequence,
                evidence_receipt_ids=(
                    evidence_receipt_ids
                ),
                accumulated_labels=accumulated_labels,
            )

        if (
            external_action
            and contains_untrusted_content
            and intent_mismatch
        ):
            return CompositionVerdict(
                dangerous=True,
                score=0.88,
                category="UNTRUSTED_EXTERNAL_ACTION",
                reason=(
                    "Untrusted content influenced an external "
                    "action that was not authorized by the user."
                ),
                risk_level=RiskLevel.HIGH,
                tool_sequence=tool_sequence,
                evidence_receipt_ids=(
                    evidence_receipt_ids
                ),
                accumulated_labels=accumulated_labels,
            )

        return CompositionVerdict(
            dangerous=False,
            score=0.10,
            category="BENIGN_COMPOSITION",
            reason=(
                "The accumulated session does not form a "
                "prohibited multi-tool effect."
            ),
            risk_level=RiskLevel.LOW,
            tool_sequence=tool_sequence,
            evidence_receipt_ids=evidence_receipt_ids,
            accumulated_labels=accumulated_labels,
        )