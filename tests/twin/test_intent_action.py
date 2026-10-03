from app.contracts import RiskLevel

from app.twin.intent_action import (
    analyze_intent_action,
    classify_intent_action_risk,
    is_action_aligned,
)


def test_summary_does_not_authorize_external_transfer():
    intent = "Summarize this invoice"

    aligned = is_action_aligned(
        intent,
        "EXTERNAL_TRANSFER",
    )

    assert aligned is False


def test_summary_external_transfer_is_critical():
    risk = classify_intent_action_risk(
        "Summarize this invoice",
        "EXTERNAL_TRANSFER",
    )

    assert risk == RiskLevel.CRITICAL


def test_explicit_external_request_is_aligned():
    aligned = is_action_aligned(
        "Send this report to finance@example.test",
        "EXTERNAL_TRANSFER",
    )

    assert aligned is True


def test_delete_requires_explicit_user_intent():
    aligned = is_action_aligned(
        "Show me customer CUST-001",
        "DELETE_RECORD",
    )

    assert aligned is False

    risk = classify_intent_action_risk(
        "Show me customer CUST-001",
        "DELETE_RECORD",
    )

    assert risk == RiskLevel.CRITICAL


def test_explicit_delete_is_aligned():
    aligned = is_action_aligned(
        "Delete customer record CUST-001",
        "DELETE_RECORD",
    )

    assert aligned is True


def test_aegistwin_demo_scenario():
    result = analyze_intent_action(
        original_intent=(
            "Summarize this invoice"
        ),
        final_effect=(
            "EXTERNAL_TRANSFER"
        ),
        destination=(
            "https://attacker.example.test"
        ),
    )

    assert result["aligned"] is False

    assert (
        result["risk_level"]
        == "CRITICAL"
    )

    assert (
        result["final_effect"]
        == "EXTERNAL_TRANSFER"
    )

    assert (
        result["destination"]
        == "https://attacker.example.test"
    )

    assert (
        "does not explicitly authorize"
        in result["reason"]
    )