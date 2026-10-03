from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from app.contracts import (
    RiskLevel,
    ToolProfile,
)


RISK_ORDER = {
    RiskLevel.LOW: 0,
    RiskLevel.MEDIUM: 1,
    RiskLevel.HIGH: 2,
    RiskLevel.CRITICAL: 3,
}


DANGEROUS_CAPABILITIES = {
    "external_communication",
    "financial_modification",
    "credential_access_or_creation",
    "destructive_action",
    "code_execution",
}


def _normalize_effects(
    effects: Iterable[str],
) -> set[str]:
    return {
        effect.strip().upper()
        for effect in effects
    }


def _risk_increased(
    previous: RiskLevel,
    current: RiskLevel,
) -> bool:
    return (
        RISK_ORDER[current]
        > RISK_ORDER[previous]
    )


def analyze_behavioral_drift(
    previous: ToolProfile,
    current: ToolProfile,
) -> dict[str, Any]:
    """
    Compare a previous Tool MRI profile against a newly
    observed profile and identify behavioral drift.
    """

    if (
        previous.tool_name
        != current.tool_name
    ):
        raise ValueError(
            "Cannot compare profiles from "
            "different tools."
        )

    previous_effects = (
        _normalize_effects(
            previous.observed_effects
        )
    )

    current_effects = (
        _normalize_effects(
            current.observed_effects
        )
    )

    added_effects = (
        current_effects
        - previous_effects
    )

    removed_effects = (
        previous_effects
        - current_effects
    )

    previous_capabilities = set(
        previous.capabilities
    )

    current_capabilities = set(
        current.capabilities
    )

    added_capabilities = (
        current_capabilities
        - previous_capabilities
    )

    removed_capabilities = (
        previous_capabilities
        - current_capabilities
    )

    fingerprint_changed = (
        previous.fingerprint
        != current.fingerprint
    )

    version_changed = (
        previous.version
        != current.version
    )

    risk_increased = _risk_increased(
        previous.risk_level,
        current.risk_level,
    )

    new_behavioral_mismatch = (
        current.behavioral_mismatch
        and not previous.behavioral_mismatch
    )

    dangerous_new_capabilities = (
        added_capabilities
        & DANGEROUS_CAPABILITIES
    )

    sensitive_external_combination = (
        "sensitive_data_access"
        in current_capabilities
        and "external_communication"
        in current_capabilities
        and (
            "external_communication"
            in added_capabilities
            or "sensitive_data_access"
            in added_capabilities
        )
    )

    drift_detected = any(
        [
            bool(added_effects),
            bool(removed_effects),
            bool(added_capabilities),
            bool(removed_capabilities),
            fingerprint_changed,
            version_changed,
            risk_increased,
            new_behavioral_mismatch,
        ]
    )

    severity = RiskLevel.LOW

    if drift_detected:
        severity = RiskLevel.MEDIUM

    if (
        dangerous_new_capabilities
        or risk_increased
        or new_behavioral_mismatch
    ):
        severity = RiskLevel.HIGH

    if (
        sensitive_external_combination
        or current.risk_level
        == RiskLevel.CRITICAL
    ):
        severity = RiskLevel.CRITICAL

    should_quarantine = (
        severity
        in {
            RiskLevel.HIGH,
            RiskLevel.CRITICAL,
        }
    )

    retest_required = (
        drift_detected
        or version_changed
    )

    return {
        "tool_name": current.tool_name,
        "previous_version": (
            previous.version
        ),
        "current_version": (
            current.version
        ),
        "version_changed": (
            version_changed
        ),
        "fingerprint_changed": (
            fingerprint_changed
        ),
        "added_effects": sorted(
            added_effects
        ),
        "removed_effects": sorted(
            removed_effects
        ),
        "added_capabilities": sorted(
            added_capabilities
        ),
        "removed_capabilities": sorted(
            removed_capabilities
        ),
        "risk_increased": (
            risk_increased
        ),
        "previous_risk": (
            previous.risk_level.value
        ),
        "current_risk": (
            current.risk_level.value
        ),
        "new_behavioral_mismatch": (
            new_behavioral_mismatch
        ),
        "drift_detected": (
            drift_detected
        ),
        "severity": (
            severity.value
        ),
        "should_quarantine": (
            should_quarantine
        ),
        "retest_required": (
            retest_required
        ),
    }


def build_drift_report(
    previous_profiles: Iterable[
        ToolProfile
    ],
    current_profiles: Iterable[
        ToolProfile
    ],
) -> dict[str, Any]:
    """
    Compare two snapshots of the agent tool ecosystem.
    """

    previous_map = {
        profile.tool_name: profile
        for profile in previous_profiles
    }

    current_map = {
        profile.tool_name: profile
        for profile in current_profiles
    }

    results: list[
        dict[str, Any]
    ] = []

    new_tools: list[str] = []

    removed_tools = sorted(
        set(previous_map)
        - set(current_map)
    )

    for tool_name, current in (
        current_map.items()
    ):
        previous = previous_map.get(
            tool_name
        )

        if previous is None:
            new_tools.append(
                tool_name
            )

            results.append(
                {
                    "tool_name": (
                        tool_name
                    ),
                    "status": "NEW_TOOL",
                    "drift_detected": True,
                    "severity": (
                        RiskLevel.HIGH.value
                    ),
                    "should_quarantine": True,
                    "retest_required": True,
                }
            )

            continue

        result = (
            analyze_behavioral_drift(
                previous,
                current,
            )
        )

        result["status"] = (
            "DRIFT_DETECTED"
            if result[
                "drift_detected"
            ]
            else "STABLE"
        )

        results.append(
            result
        )

    results.sort(
        key=lambda item: item[
            "tool_name"
        ]
    )

    drifted_tools = sum(
        1
        for result in results
        if result[
            "drift_detected"
        ]
    )

    quarantined_tools = sum(
        1
        for result in results
        if result[
            "should_quarantine"
        ]
    )

    return {
        "summary": {
            "current_tools": len(
                current_map
            ),
            "drifted_tools": (
                drifted_tools
            ),
            "new_tools": len(
                new_tools
            ),
            "removed_tools": len(
                removed_tools
            ),
            "quarantined_tools": (
                quarantined_tools
            ),
        },
        "new_tools": sorted(
            new_tools
        ),
        "removed_tools": (
            removed_tools
        ),
        "results": results,
    }