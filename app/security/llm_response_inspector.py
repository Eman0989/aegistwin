
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


def inspect_response(content: str) -> ResponseInspection:
    """Apply basic deterministic redaction to model text."""

    if not isinstance(content, str):
        return ResponseInspection(
            action=ResponseAction.BLOCK,
            content=None,
            reason="Invalid model response content.",
        )

    artifact = DataArtifact(
        artifact_id="llm-response",
        value=content,
        labels=set(),
    )

    try:
        result = redact_artifacts([artifact])
    except (TypeError, ValueError):
        return ResponseInspection(
            action=ResponseAction.BLOCK,
            content=None,
            reason="Response inspection failed.",
        )

    if not result.changed:
        return ResponseInspection(
            action=ResponseAction.ALLOW,
            content=content,
            reason="No supported sensitive-data pattern detected.",
        )

    sanitized = result.artifacts[0].value

    if not isinstance(sanitized, str) or sanitized == content:
        return ResponseInspection(
            action=ResponseAction.BLOCK,
            content=None,
            reason="Required redaction could not be completed.",
        )

    return ResponseInspection(
        action=ResponseAction.REDACT,
        content=sanitized,
        reason="Supported sensitive data was redacted.",
    )
