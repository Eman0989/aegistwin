from __future__ import annotations

from typing import Any, Iterable

from app.contracts import (
    InstructionOrigin,
    RiskLevel,
    ToolCall,
)


TRUSTED_ORIGINS = {
    InstructionOrigin.USER,
    InstructionOrigin.SYSTEM,
    InstructionOrigin.TRUSTED_INTERNAL,
}


UNTRUSTED_ORIGINS = {
    InstructionOrigin.WEB_UNTRUSTED,
    InstructionOrigin.DOCUMENT_UNTRUSTED,
    InstructionOrigin.EMAIL_UNTRUSTED,
    InstructionOrigin.MCP_TOOL_OUTPUT,
    InstructionOrigin.EXTERNAL_API,
}


SENSITIVE_EFFECTS = {
    "EXTERNAL_TRANSFER",
    "SEND_EXTERNAL_DATA",
    "FINANCIAL_MODIFICATION",
    "CREATE_CREDENTIAL",
    "DELETE_RECORD",
    "DELETE_FILE",
    "DESTRUCTIVE_ACTION",
    "EXECUTE_CODE",
    "MODIFY_PERMISSION",
}


def is_trusted_origin(
    origin: InstructionOrigin,
) -> bool:
    """
    Return True when the instruction originated from
    a trusted authorization source.
    """

    return origin in TRUSTED_ORIGINS


def is_untrusted_origin(
    origin: InstructionOrigin,
) -> bool:
    """
    Return True when the instruction originated from
    untrusted or externally controlled content.
    """

    return origin in UNTRUSTED_ORIGINS


def can_authorize_sensitive_action(
    origin: InstructionOrigin,
) -> bool:
    """
    Determine whether an instruction source may authorize
    a sensitive action.

    Important AegisTwin rule:

    Untrusted content is DATA, not authorization.
    """

    return origin in TRUSTED_ORIGINS


def classify_provenance_risk(
    origin: InstructionOrigin,
    requested_effect: str | None = None,
) -> RiskLevel:
    """
    Classify provenance risk.

    An untrusted instruction trying to trigger a sensitive
    effect is considered CRITICAL.
    """

    normalized_effect = (
        requested_effect.strip().upper()
        if requested_effect
        else None
    )

    if (
        origin in UNTRUSTED_ORIGINS
        and normalized_effect in SENSITIVE_EFFECTS
    ):
        return RiskLevel.CRITICAL

    if origin in UNTRUSTED_ORIGINS:
        return RiskLevel.HIGH

    if origin == InstructionOrigin.USER:
        return RiskLevel.LOW

    if origin in {
        InstructionOrigin.SYSTEM,
        InstructionOrigin.TRUSTED_INTERNAL,
    }:
        return RiskLevel.LOW

    return RiskLevel.MEDIUM


def analyze_tool_call_provenance(
    call: ToolCall,
    requested_effect: str | None = None,
) -> dict[str, Any]:
    """
    Produce a serializable provenance analysis for one ToolCall.

    This object is intentionally frontend-friendly and can later
    be included in the Twin graph or security report.
    """

    trusted = is_trusted_origin(
        call.instruction_origin
    )

    can_authorize = (
        can_authorize_sensitive_action(
            call.instruction_origin
        )
    )

    risk_level = classify_provenance_risk(
        call.instruction_origin,
        requested_effect,
    )

    return {
        "call_id": call.call_id,
        "session_id": call.session_id,
        "tool_name": call.tool_name,
        "original_user_intent": (
            call.original_user_intent
        ),
        "instruction_origin": (
            call.instruction_origin.value
        ),
        "trusted": trusted,
        "can_authorize_sensitive_action": (
            can_authorize
        ),
        "requested_effect": requested_effect,
        "risk_level": risk_level.value,
    }


def most_restrictive_origin(
    origins: Iterable[InstructionOrigin],
) -> InstructionOrigin:
    """
    Determine the most security-sensitive origin in a chain.

    If any untrusted source influenced the instruction chain,
    preserve that untrusted provenance instead of silently
    upgrading it to trusted.

    Priority is intentionally conservative.
    """

    origins = list(origins)

    if not origins:
        return InstructionOrigin.SYSTEM

    priority = (
        InstructionOrigin.WEB_UNTRUSTED,
        InstructionOrigin.DOCUMENT_UNTRUSTED,
        InstructionOrigin.EMAIL_UNTRUSTED,
        InstructionOrigin.MCP_TOOL_OUTPUT,
        InstructionOrigin.EXTERNAL_API,
        InstructionOrigin.USER,
        InstructionOrigin.TRUSTED_INTERNAL,
        InstructionOrigin.SYSTEM,
    )

    for origin in priority:
        if origin in origins:
            return origin

    return origins[0]


def build_provenance_chain(
    calls: Iterable[ToolCall],
) -> dict[str, Any]:
    """
    Summarize the provenance of a multi-tool workflow.
    """

    calls = list(calls)

    if not calls:
        return {
            "call_count": 0,
            "origins": [],
            "effective_origin": (
                InstructionOrigin.SYSTEM.value
            ),
            "contains_untrusted_content": False,
            "can_authorize_sensitive_action": True,
            "risk_level": RiskLevel.LOW.value,
        }

    origins = [
        call.instruction_origin
        for call in calls
    ]

    effective_origin = (
        most_restrictive_origin(origins)
    )

    contains_untrusted = any(
        is_untrusted_origin(origin)
        for origin in origins
    )

    return {
        "call_count": len(calls),
        "origins": [
            origin.value
            for origin in origins
        ],
        "effective_origin": (
            effective_origin.value
        ),
        "contains_untrusted_content": (
            contains_untrusted
        ),
        "can_authorize_sensitive_action": (
            can_authorize_sensitive_action(
                effective_origin
            )
        ),
        "risk_level": (
            classify_provenance_risk(
                effective_origin
            ).value
        ),
    }