
"""Standalone inspection of LLM-generated text."""

from dataclasses import dataclass
from enum import Enum

from app.contracts import DataArtifact
from app.security.redaction import redact_artifacts


class ResponseAction(str, Enum):
    ALLOW = "ALLOW"
    REDACT = "REDACT"
    BLOCK = "BLOCK"


@dataclass(frozen=True)
class ResponseInspection:
    action: ResponseAction
    content: str | None
    reason: str
    matched_rules: tuple[str, ...] = ()
    redaction_count: int = 0


def inspect_response(content: str) -> ResponseInspection:
    """Apply limited deterministic email redaction to model text."""

    def block(reason: str) -> ResponseInspection:
        return ResponseInspection(
            action=ResponseAction.BLOCK,
            content=None,
            reason=reason,
        )

    if not isinstance(content, str):
        return block("Invalid model response content.")

    artifact = DataArtifact(
        artifact_id="llm-response",
        value=content,
        labels=set(),
    )

    try:
        result = redact_artifacts([artifact])

        # Validate the redactor's result before using it.
        if not isinstance(result.changed, bool):
            return block("Invalid redaction result.")

        if not isinstance(result.artifacts, list):
            return block("Invalid redaction artifacts.")

        if len(result.artifacts) != 1:
            return block("Unexpected number of redaction artifacts.")

        sanitized = result.artifacts[0].value

        if not isinstance(sanitized, str):
            return block("Invalid sanitized content.")

        if not isinstance(result.redacted_value_count, int):
            return block("Invalid redaction count.")

        if result.changed:
            if (
                result.redacted_value_count <= 0
                or sanitized == content
            ):
                return block(
                    "Required redaction could not be completed."
                )

            return ResponseInspection(
                action=ResponseAction.REDACT,
                content=sanitized,
                reason="Supported sensitive data was redacted.",
                matched_rules=("email",),
                redaction_count=result.redacted_value_count,
            )

        # An unchanged result must not report redactions
        # or silently modify the original content.
        if (
            result.redacted_value_count != 0
            or sanitized != content
        ):
            return block("Inconsistent redaction result.")

        return ResponseInspection(
            action=ResponseAction.ALLOW,
            content=content,
            reason="No supported sensitive-data pattern detected.",
        )

    except (TypeError, ValueError, IndexError, AttributeError):
        return block("Response inspection failed.")
