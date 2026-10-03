from __future__ import annotations

from typing import Any

from app.contracts import RiskLevel


EXTERNAL_ACTIONS = {
    "EXTERNAL_TRANSFER",
    "SEND_EXTERNAL_DATA",
    "SEND_HTTP_REQUEST",
    "UPLOAD_EXTERNAL",
}

FINANCIAL_ACTIONS = {
    "TRANSFER_MONEY",
    "MODIFY_PAYMENT",
    "CREATE_PAYMENT",
}

DESTRUCTIVE_ACTIONS = {
    "DELETE_RECORD",
    "DELETE_FILE",
    "DROP_DATABASE",
    "DESTRUCTIVE_ACTION",
}

CREDENTIAL_ACTIONS = {
    "CREATE_CREDENTIAL",
    "MODIFY_CREDENTIAL",
    "RESET_PASSWORD",
}

CODE_EXECUTION_ACTIONS = {
    "EXECUTE_CODE",
    "RUN_SUBPROCESS",
    "SHELL_EXECUTION",
}


def _normalize(value: str) -> str:
    return value.strip().upper()


def _contains_any(
    text: str,
    keywords: set[str],
) -> bool:
    text = text.lower()

    return any(
        keyword.lower() in text
        for keyword in keywords
    )


def _explicit_external_intent(
    intent: str,
) -> bool:
    """
    Detect whether the user explicitly asked for data
    to be sent outside the current trust boundary.
    """

    text = intent.lower()

    external_verbs = {
        "send",
        "upload",
        "post",
        "transfer",
        "email",
        "share",
        "forward",
    }

    has_external_verb = any(
        verb in text
        for verb in external_verbs
    )

    has_destination_marker = (
        " to " in text
        or "@" in text
        or "http://" in text
        or "https://" in text
    )

    return (
        has_external_verb
        and has_destination_marker
    )


def _explicit_financial_intent(
    intent: str,
) -> bool:
    keywords = {
        "transfer money",
        "make payment",
        "pay ",
        "send money",
        "modify payment",
    }

    return _contains_any(
        intent,
        keywords,
    )


def _explicit_destructive_intent(
    intent: str,
) -> bool:
    keywords = {
        "delete",
        "remove record",
        "drop database",
        "erase",
    }

    return _contains_any(
        intent,
        keywords,
    )


def _explicit_credential_intent(
    intent: str,
) -> bool:
    keywords = {
        "create credential",
        "create account",
        "reset password",
        "change password",
        "generate api key",
    }

    return _contains_any(
        intent,
        keywords,
    )


def _explicit_code_execution_intent(
    intent: str,
) -> bool:
    keywords = {
        "execute code",
        "run script",
        "run command",
        "execute command",
        "run program",
    }

    return _contains_any(
        intent,
        keywords,
    )


def is_action_aligned(
    original_intent: str,
    final_effect: str,
) -> bool:
    """
    Determine whether the observed final action is
    consistent with the user's original request.
    """

    effect = _normalize(
        final_effect
    )

    if effect in EXTERNAL_ACTIONS:
        return _explicit_external_intent(
            original_intent
        )

    if effect in FINANCIAL_ACTIONS:
        return _explicit_financial_intent(
            original_intent
        )

    if effect in DESTRUCTIVE_ACTIONS:
        return _explicit_destructive_intent(
            original_intent
        )

    if effect in CREDENTIAL_ACTIONS:
        return _explicit_credential_intent(
            original_intent
        )

    if effect in CODE_EXECUTION_ACTIONS:
        return _explicit_code_execution_intent(
            original_intent
        )

    # Normal non-sensitive actions are considered aligned
    # unless another rule explicitly says otherwise.
    return True


def classify_intent_action_risk(
    original_intent: str,
    final_effect: str,
) -> RiskLevel:
    """
    Classify the security risk caused by an
    intent-versus-action mismatch.
    """

    effect = _normalize(
        final_effect
    )

    aligned = is_action_aligned(
        original_intent,
        final_effect,
    )

    if aligned:
        return RiskLevel.LOW

    if (
        effect in EXTERNAL_ACTIONS
        or effect in FINANCIAL_ACTIONS
        or effect in DESTRUCTIVE_ACTIONS
        or effect in CREDENTIAL_ACTIONS
    ):
        return RiskLevel.CRITICAL

    if effect in CODE_EXECUTION_ACTIONS:
        return RiskLevel.HIGH

    return RiskLevel.MEDIUM


def explain_intent_mismatch(
    original_intent: str,
    final_effect: str,
) -> str:
    """
    Generate a human-readable explanation suitable
    for logs, reports and the dashboard.
    """

    effect = _normalize(
        final_effect
    )

    if is_action_aligned(
        original_intent,
        final_effect,
    ):
        return (
            "The observed action is consistent with "
            "the user's original request."
        )

    if effect in EXTERNAL_ACTIONS:
        return (
            "The user's request does not explicitly authorize "
            "transferring data outside the current trust boundary."
        )

    if effect in FINANCIAL_ACTIONS:
        return (
            "The user's request does not explicitly authorize "
            "a financial modification."
        )

    if effect in DESTRUCTIVE_ACTIONS:
        return (
            "The user's request does not explicitly authorize "
            "a destructive action."
        )

    if effect in CREDENTIAL_ACTIONS:
        return (
            "The user's request does not explicitly authorize "
            "credential creation or modification."
        )

    if effect in CODE_EXECUTION_ACTIONS:
        return (
            "The user's request does not explicitly authorize "
            "code or command execution."
        )

    return (
        "The observed effect is not clearly required "
        "to satisfy the user's original intent."
    )


def analyze_intent_action(
    *,
    original_intent: str,
    final_effect: str,
    destination: str | None = None,
) -> dict[str, Any]:
    """
    Return a JSON-serializable intent-versus-action
    security analysis.
    """

    aligned = is_action_aligned(
        original_intent,
        final_effect,
    )

    risk_level = classify_intent_action_risk(
        original_intent,
        final_effect,
    )

    return {
        "original_intent": original_intent,
        "final_effect": _normalize(
            final_effect
        ),
        "destination": destination,
        "aligned": aligned,
        "risk_level": risk_level.value,
        "reason": explain_intent_mismatch(
            original_intent,
            final_effect,
        ),
    }