from __future__ import annotations

from typing import Any, Iterable

from app.contracts import ToolProfile


CAPABILITY_CATEGORIES = (
    "sensitive_data_access",
    "external_communication",
    "financial_modification",
    "credential_access_or_creation",
    "destructive_action",
    "code_execution",
    "filesystem_access",
    "database_access",
)


def build_tool_capability_entry(
    profile: ToolProfile,
) -> dict[str, Any]:
    """
    Convert one ToolProfile into a frontend-friendly capability record.
    """

    capabilities = set(profile.capabilities)

    capability_flags = {
        capability: capability in capabilities
        for capability in CAPABILITY_CATEGORIES
    }

    return {
        "tool_name": profile.tool_name,
        "version": profile.version,
        "risk_level": profile.risk_level.value,
        "behavioral_mismatch": profile.behavioral_mismatch,
        "fingerprint": profile.fingerprint,
        "declared_effects": sorted(profile.declared_effects),
        "observed_effects": sorted(profile.observed_effects),
        "capabilities": sorted(profile.capabilities),
        "capability_flags": capability_flags,
    }


def build_capability_map(
    profiles: Iterable[ToolProfile],
) -> dict[str, Any]:
    """
    Build a complete capability map for all observed tools.
    """

    tools = [
        build_tool_capability_entry(profile)
        for profile in profiles
    ]

    tools.sort(
        key=lambda item: item["tool_name"]
    )

    summary = {
        "total_tools": len(tools),
        "critical_tools": sum(
            1
            for tool in tools
            if tool["risk_level"] == "CRITICAL"
        ),
        "high_risk_tools": sum(
            1
            for tool in tools
            if tool["risk_level"] == "HIGH"
        ),
        "behavioral_mismatches": sum(
            1
            for tool in tools
            if tool["behavioral_mismatch"]
        ),
        "external_communication_tools": sum(
            1
            for tool in tools
            if tool["capability_flags"][
                "external_communication"
            ]
        ),
        "sensitive_data_tools": sum(
            1
            for tool in tools
            if tool["capability_flags"][
                "sensitive_data_access"
            ]
        ),
    }

    return {
        "summary": summary,
        "tools": tools,
    }