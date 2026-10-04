"""Deterministic sensitive-data redaction for AegisTwin.

The redactor transforms copies of DataArtifact objects before execution.
Original artifacts remain untouched so the security decision and evidence
continue to represent what the agent originally attempted to use.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.config import SENSITIVE_LABELS
from app.contracts import DataArtifact


REDACTED_VALUE = "[REDACTED]"

_EMAIL_PATTERN = re.compile(
    r"\b[A-Za-z0-9._%+-]+"
    r"@[A-Za-z0-9.-]+"
    r"\.[A-Za-z]{2,}\b"
)

_SENSITIVE_KEYS = {
    "email",
    "e-mail",
    "password",
    "passwd",
    "secret",
    "credential",
    "credentials",
    "api_key",
    "api-key",
    "apikey",
    "access_token",
    "access-token",
    "token",
}


@dataclass(frozen=True)
class RedactionResult:
    """Summary of one deterministic redaction operation."""

    artifacts: list[DataArtifact]
    redacted_value_count: int
    changed_artifact_count: int
    original_artifact_ids: list[str]
    sanitized_artifact_ids: list[str]

    @property
    def changed(self) -> bool:
        return self.redacted_value_count > 0


def _redact_value(
    value: Any,
    *,
    key: str | None = None,
) -> tuple[Any, int]:
    """Recursively redact deterministic sensitive values."""

    if (
        key is not None
        and key.lower() in _SENSITIVE_KEYS
        and value not in {
            None,
            "",
            REDACTED_VALUE,
        }
    ):
        return REDACTED_VALUE, 1

    if isinstance(value, str):
        redacted, count = _EMAIL_PATTERN.subn(
            REDACTED_VALUE,
            value,
        )
        return redacted, count

    if isinstance(value, dict):
        result: dict[Any, Any] = {}
        total = 0

        for child_key, child_value in value.items():
            redacted_child, child_count = _redact_value(
                child_value,
                key=str(child_key),
            )

            result[child_key] = redacted_child
            total += child_count

        return result, total

    if isinstance(value, list):
        result_list: list[Any] = []
        total = 0

        for child in value:
            redacted_child, child_count = _redact_value(
                child
            )

            result_list.append(redacted_child)
            total += child_count

        return result_list, total

    if isinstance(value, tuple):
        result_tuple: list[Any] = []
        total = 0

        for child in value:
            redacted_child, child_count = _redact_value(
                child
            )

            result_tuple.append(redacted_child)
            total += child_count

        return tuple(result_tuple), total

    return value, 0


def redact_artifacts(
    artifacts: list[DataArtifact],
) -> RedactionResult:
    """Create sanitized artifact copies while preserving lineage."""

    sanitized: list[DataArtifact] = []

    redacted_value_count = 0
    changed_artifact_count = 0

    original_artifact_ids: list[str] = []
    sanitized_artifact_ids: list[str] = []

    for artifact in artifacts:
        original_artifact_ids.append(
            artifact.artifact_id
        )

        redacted_value, value_count = _redact_value(
            artifact.value
        )

        sensitive = bool(
            artifact.labels.intersection(
                SENSITIVE_LABELS
            )
        )

        changed = value_count > 0

        if changed:
            changed_artifact_count += 1
            redacted_value_count += value_count

            remaining_labels = (
                set(artifact.labels)
                - SENSITIVE_LABELS
            )

            remaining_labels.add("REDACTED")

            sanitized_artifact = DataArtifact(
                artifact_id=(
                    f"redacted-{artifact.artifact_id}"
                ),
                value=redacted_value,
                labels=remaining_labels,
                parent_artifact_ids=[
                    artifact.artifact_id
                ],
                transformation="redact",
            )

            sanitized.append(
                sanitized_artifact
            )

            sanitized_artifact_ids.append(
                sanitized_artifact.artifact_id
            )

            continue

        # If policy requested REDACT because the artifact is
        # sensitive, but the deterministic redactor could not
        # identify an actual value, keep the artifact unchanged.
        # The gateway will fail closed when no redaction occurred.
        sanitized.append(artifact)

        sanitized_artifact_ids.append(
            artifact.artifact_id
        )

    return RedactionResult(
        artifacts=sanitized,
        redacted_value_count=redacted_value_count,
        changed_artifact_count=changed_artifact_count,
        original_artifact_ids=original_artifact_ids,
        sanitized_artifact_ids=sanitized_artifact_ids,
    )