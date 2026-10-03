from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable

from app.contracts import EffectReceipt, RiskLevel, ToolProfile


SENSITIVE_LABELS = {
    "CustomerPII",
    "DerivedFrom<CustomerPII>",
    "SECRET",
    "CONFIDENTIAL",
}

EXTERNAL_EFFECTS = {
    "EXTERNAL_NETWORK",
    "SEND_HTTP_REQUEST",
    "HTTP_POST",
    "EXTERNAL_TRANSFER",
}

DATABASE_EFFECTS = {
    "READ_DATABASE",
    "WRITE_DATABASE",
    "READ_CUSTOMER_RECORD",
    "READ_CUSTOMER_PII",
}

FILESYSTEM_EFFECTS = {
    "READ_FILE",
    "WRITE_FILE",
    "FILESYSTEM_ACCESS",
}

FINANCIAL_EFFECTS = {
    "TRANSFER_MONEY",
    "MODIFY_PAYMENT",
    "FINANCIAL_MODIFICATION",
}

CREDENTIAL_EFFECTS = {
    "CREATE_CREDENTIAL",
    "MODIFY_CREDENTIAL",
    "READ_CREDENTIAL",
}

DESTRUCTIVE_EFFECTS = {
    "DELETE_RECORD",
    "DELETE_FILE",
    "DROP_DATABASE",
    "DESTRUCTIVE_ACTION",
}

CODE_EXECUTION_EFFECTS = {
    "EXECUTE_CODE",
    "RUN_SUBPROCESS",
    "SHELL_EXECUTION",
}


def _normalize_effect(effect: str) -> str:
    """Convert effect names to a consistent format."""
    return effect.strip().upper()


def _collect_observed_effects(
    receipts: Iterable[EffectReceipt],
    tool_name: str,
) -> tuple[set[str], set[str]]:
    """
    Collect observed effects and data labels for one tool.

    Tool MRI analyzes EffectReceipts produced by the runtime layer.
    It does not execute tools itself.
    """

    observed_effects: set[str] = set()
    data_labels: set[str] = set()

    for receipt in receipts:
        if receipt.call.tool_name != tool_name:
            continue

        for effect in receipt.observed_effects:
            observed_effects.add(
                _normalize_effect(effect.effect_type)
            )

            data_labels.update(effect.data_labels)

            destination_class = str(
                effect.metadata.get(
                    "destination_class",
                    "",
                )
            ).upper()

            if destination_class == "EXTERNAL":
                observed_effects.add(
                    "EXTERNAL_NETWORK"
                )

    return observed_effects, data_labels


def _detect_capabilities(
    observed_effects: set[str],
    data_labels: set[str],
) -> set[str]:
    """
    Convert observed behavior into normalized capability classes.
    """

    capabilities: set[str] = set()

    sensitive_data_access = any(
        label in SENSITIVE_LABELS
        or label.startswith("DerivedFrom<")
        for label in data_labels
    )

    if sensitive_data_access:
        capabilities.add(
            "sensitive_data_access"
        )

    if observed_effects & EXTERNAL_EFFECTS:
        capabilities.add(
            "external_communication"
        )

    if observed_effects & DATABASE_EFFECTS:
        capabilities.add(
            "database_access"
        )

    if observed_effects & FILESYSTEM_EFFECTS:
        capabilities.add(
            "filesystem_access"
        )

    if observed_effects & FINANCIAL_EFFECTS:
        capabilities.add(
            "financial_modification"
        )

    if observed_effects & CREDENTIAL_EFFECTS:
        capabilities.add(
            "credential_access_or_creation"
        )

    if observed_effects & DESTRUCTIVE_EFFECTS:
        capabilities.add(
            "destructive_action"
        )

    if observed_effects & CODE_EXECUTION_EFFECTS:
        capabilities.add(
            "code_execution"
        )

    return capabilities


def _calculate_risk(
    capabilities: set[str],
) -> RiskLevel:
    """
    Deterministic and explainable MVP risk model.
    """

    if (
        "sensitive_data_access" in capabilities
        and
        "external_communication" in capabilities
    ):
        return RiskLevel.CRITICAL

    if (
        "destructive_action" in capabilities
        or
        "financial_modification" in capabilities
    ):
        return RiskLevel.CRITICAL

    if (
        "credential_access_or_creation" in capabilities
        or
        "code_execution" in capabilities
    ):
        return RiskLevel.HIGH

    if "external_communication" in capabilities:
        return RiskLevel.HIGH

    if (
        "sensitive_data_access" in capabilities
        or
        "database_access" in capabilities
        or
        "filesystem_access" in capabilities
    ):
        return RiskLevel.MEDIUM

    return RiskLevel.LOW


def _generate_fingerprint(
    tool_name: str,
    version: str,
    observed_effects: set[str],
    capabilities: set[str],
) -> str:
    """
    Generate a stable SHA-256 fingerprint of observed tool behavior.
    """

    payload = {
        "tool_name": tool_name,
        "version": version,
        "observed_effects": sorted(
            observed_effects
        ),
        "capabilities": sorted(
            capabilities
        ),
    }

    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    return hashlib.sha256(
        encoded
    ).hexdigest()


def find_behavior_mismatches(
    profile: ToolProfile,
) -> list[str]:
    """
    Find effects that happened at runtime but were not declared
    by the tool.

    Example:

    Declared:
        READ_INVOICE

    Observed:
        READ_INVOICE
        READ_CUSTOMER_PII
        SEND_HTTP_REQUEST

    Mismatch:
        READ_CUSTOMER_PII
        SEND_HTTP_REQUEST
    """

    declared = {
        _normalize_effect(effect)
        for effect in profile.declared_effects
    }

    observed = {
        _normalize_effect(effect)
        for effect in profile.observed_effects
    }

    return sorted(
        observed - declared
    )


def has_behavior_mismatch(
    profile: ToolProfile,
) -> bool:
    """Return True if runtime behavior exceeds declared behavior."""

    return bool(
        find_behavior_mismatches(profile)
    )


def analyze_tool(
    declared_profile: ToolProfile,
    receipts: Iterable[EffectReceipt],
) -> ToolProfile:
    """
    Build the empirical Tool MRI profile.

    Input:
        Declared ToolProfile
        +
        runtime EffectReceipts

    Output:
        ToolProfile containing actual observed effects,
        capabilities, risk, mismatch status and fingerprint.
    """

    observed_effects, data_labels = (
        _collect_observed_effects(
            receipts,
            declared_profile.tool_name,
        )
    )

    capabilities = _detect_capabilities(
        observed_effects,
        data_labels,
    )

    risk_level = _calculate_risk(
        capabilities
    )

    declared_effects = {
        _normalize_effect(effect)
        for effect
        in declared_profile.declared_effects
    }

    mismatches = (
        observed_effects
        - declared_effects
    )

    fingerprint = _generate_fingerprint(
        tool_name=declared_profile.tool_name,
        version=declared_profile.version,
        observed_effects=observed_effects,
        capabilities=capabilities,
    )

    return ToolProfile(
        tool_name=declared_profile.tool_name,
        version=declared_profile.version,
        declared_effects=declared_effects,
        observed_effects=observed_effects,
        capabilities=capabilities,
        risk_level=risk_level,
        behavioral_mismatch=bool(
            mismatches
        ),
        fingerprint=fingerprint,
    )