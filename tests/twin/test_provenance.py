from datetime import datetime, timezone

from app.contracts import (
    InstructionOrigin,
    RiskLevel,
    ToolCall,
)

from app.twin.provenance import (
    analyze_tool_call_provenance,
    build_provenance_chain,
    can_authorize_sensitive_action,
    classify_provenance_risk,
    is_trusted_origin,
    is_untrusted_origin,
    most_restrictive_origin,
)


def make_call(
    call_id: str,
    tool_name: str,
    origin: InstructionOrigin,
) -> ToolCall:
    return ToolCall(
        call_id=call_id,
        session_id="session-001",
        tool_name=tool_name,
        arguments={},
        instruction_origin=origin,
        original_user_intent=(
            "Summarize this invoice"
        ),
        timestamp=datetime.now(
            timezone.utc
        ),
    )


def test_untrusted_web_cannot_authorize_sensitive_action():
    origin = (
        InstructionOrigin.WEB_UNTRUSTED
    )

    assert is_untrusted_origin(origin) is True
    assert is_trusted_origin(origin) is False

    assert (
        can_authorize_sensitive_action(
            origin
        )
        is False
    )


def test_user_origin_can_authorize_action():
    origin = InstructionOrigin.USER

    assert is_trusted_origin(origin) is True

    assert (
        can_authorize_sensitive_action(
            origin
        )
        is True
    )


def test_untrusted_external_transfer_is_critical():
    risk = classify_provenance_risk(
        InstructionOrigin.WEB_UNTRUSTED,
        "EXTERNAL_TRANSFER",
    )

    assert risk == RiskLevel.CRITICAL


def test_analyze_tool_call_provenance():
    call = make_call(
        call_id="call-001",
        tool_name="external_http",
        origin=(
            InstructionOrigin.WEB_UNTRUSTED
        ),
    )

    result = (
        analyze_tool_call_provenance(
            call,
            requested_effect=(
                "EXTERNAL_TRANSFER"
            ),
        )
    )

    assert (
        result["instruction_origin"]
        == "WEB_UNTRUSTED"
    )

    assert result["trusted"] is False

    assert (
        result[
            "can_authorize_sensitive_action"
        ]
        is False
    )

    assert (
        result["risk_level"]
        == "CRITICAL"
    )


def test_untrusted_origin_survives_workflow_chain():
    user_call = make_call(
        call_id="call-001",
        tool_name="invoice_reader",
        origin=InstructionOrigin.USER,
    )

    webpage_call = make_call(
        call_id="call-002",
        tool_name="customer_database",
        origin=(
            InstructionOrigin.WEB_UNTRUSTED
        ),
    )

    tool_call = make_call(
        call_id="call-003",
        tool_name="summarizer",
        origin=(
            InstructionOrigin.MCP_TOOL_OUTPUT
        ),
    )

    result = build_provenance_chain(
        [
            user_call,
            webpage_call,
            tool_call,
        ]
    )

    assert result["call_count"] == 3

    assert (
        result[
            "contains_untrusted_content"
        ]
        is True
    )

    assert (
        result["effective_origin"]
        == "WEB_UNTRUSTED"
    )

    assert (
        result[
            "can_authorize_sensitive_action"
        ]
        is False
    )


def test_most_restrictive_origin():
    result = most_restrictive_origin(
        [
            InstructionOrigin.USER,
            InstructionOrigin.TRUSTED_INTERNAL,
            InstructionOrigin.WEB_UNTRUSTED,
        ]
    )

    assert (
        result
        == InstructionOrigin.WEB_UNTRUSTED
    )