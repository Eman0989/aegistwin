from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from app.contracts import ToolProfile


EFFECT_CAPABILITY_REQUIREMENTS = {
    # Database
    "READ_CUSTOMER_RECORD": {
        "database_access",
    },
    "READ_DATABASE": {
        "database_access",
    },
    "WRITE_DATABASE": {
        "database_access",
    },

    # Sensitive data
    "READ_CUSTOMER_PII": {
        "database_access",
        "sensitive_data_access",
    },
    "READ_SECRET": {
        "sensitive_data_access",
    },

    # External communication
    "SEND_HTTP_REQUEST": {
        "external_communication",
    },
    "HTTP_POST": {
        "external_communication",
    },
    "EXTERNAL_TRANSFER": {
        "external_communication",
    },
    "SEND_EXTERNAL_DATA": {
        "external_communication",
    },
    "EXTERNAL_NETWORK": {
        "external_communication",
    },

    # Filesystem
    "READ_FILE": {
        "filesystem_access",
    },
    "WRITE_FILE": {
        "filesystem_access",
    },
    "DELETE_FILE": {
        "filesystem_access",
        "destructive_action",
    },

    # Financial
    "TRANSFER_MONEY": {
        "financial_modification",
    },
    "CREATE_PAYMENT": {
        "financial_modification",
    },
    "MODIFY_PAYMENT": {
        "financial_modification",
    },

    # Credentials
    "CREATE_CREDENTIAL": {
        "credential_access_or_creation",
    },
    "MODIFY_CREDENTIAL": {
        "credential_access_or_creation",
    },
    "RESET_PASSWORD": {
        "credential_access_or_creation",
    },

    # Destructive
    "DELETE_RECORD": {
        "destructive_action",
    },
    "DROP_DATABASE": {
        "database_access",
        "destructive_action",
    },

    # Code execution
    "EXECUTE_CODE": {
        "code_execution",
    },
    "RUN_SUBPROCESS": {
        "code_execution",
    },
    "SHELL_EXECUTION": {
        "code_execution",
    },
}


def _normalize(
    value: str,
) -> str:
    return value.strip().upper()


def infer_required_capabilities(
    effects: Iterable[str],
) -> set[str]:
    """
    Infer the minimum capabilities required to perform
    a set of legitimate effects.
    """

    required: set[str] = set()

    for effect in effects:
        normalized = _normalize(
            effect
        )

        required.update(
            EFFECT_CAPABILITY_REQUIREMENTS.get(
                normalized,
                set(),
            )
        )

    return required


def find_excess_capabilities(
    profile: ToolProfile,
    required_capabilities: Iterable[str],
) -> set[str]:
    """
    Capabilities currently available to the tool but
    unnecessary for the legitimate workflow.
    """

    required = set(
        required_capabilities
    )

    return (
        set(profile.capabilities)
        - required
    )


def find_missing_capabilities(
    profile: ToolProfile,
    required_capabilities: Iterable[str],
) -> set[str]:
    """
    Capabilities required by the legitimate workflow
    but not present on the current profile.
    """

    required = set(
        required_capabilities
    )

    return (
        required
        - set(profile.capabilities)
    )


def analyze_least_privilege(
    profile: ToolProfile,
    *,
    legitimate_effects: Iterable[str],
) -> dict[str, Any]:
    """
    Produce a least-privilege recommendation for one tool.
    """

    legitimate_effects = {
        _normalize(effect)
        for effect in legitimate_effects
    }

    required_capabilities = (
        infer_required_capabilities(
            legitimate_effects
        )
    )

    current_capabilities = set(
        profile.capabilities
    )

    removable = (
        find_excess_capabilities(
            profile,
            required_capabilities,
        )
    )

    missing = (
        find_missing_capabilities(
            profile,
            required_capabilities,
        )
    )

    current_count = len(
        current_capabilities
    )

    reduction_percent = 0.0

    if current_count:
        reduction_percent = round(
            (
                len(removable)
                / current_count
            )
            * 100,
            2,
        )

    return {
        "tool_name": profile.tool_name,
        "current_capabilities": sorted(
            current_capabilities
        ),
        "required_capabilities": sorted(
            required_capabilities
        ),
        "removable_capabilities": sorted(
            removable
        ),
        "missing_capabilities": sorted(
            missing
        ),
        "legitimate_effects": sorted(
            legitimate_effects
        ),
        "least_privilege_satisfied": (
            not removable
            and not missing
        ),
        "reduction_percent": (
            reduction_percent
        ),
    }


def build_least_privilege_plan(
    profiles: Iterable[ToolProfile],
    legitimate_effects_by_tool: dict[
        str,
        Iterable[str],
    ],
) -> dict[str, Any]:
    """
    Build a complete least-privilege plan across
    the observed agent toolset.
    """

    recommendations: list[
        dict[str, Any]
    ] = []

    for profile in profiles:
        legitimate_effects = (
            legitimate_effects_by_tool.get(
                profile.tool_name,
                (),
            )
        )

        recommendations.append(
            analyze_least_privilege(
                profile,
                legitimate_effects=(
                    legitimate_effects
                ),
            )
        )

    recommendations.sort(
        key=lambda item: item[
            "tool_name"
        ]
    )

    tools_with_excess = sum(
        1
        for recommendation
        in recommendations
        if recommendation[
            "removable_capabilities"
        ]
    )

    total_removable = sum(
        len(
            recommendation[
                "removable_capabilities"
            ]
        )
        for recommendation
        in recommendations
    )

    return {
        "summary": {
            "total_tools": len(
                recommendations
            ),
            "tools_with_excess_privilege": (
                tools_with_excess
            ),
            "total_removable_capabilities": (
                total_removable
            ),
        },
        "recommendations": recommendations,
    }