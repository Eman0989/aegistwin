from app.contracts import InstructionOrigin, ToolCall


def test_tool_call_defaults_timestamp():
    call = ToolCall(
        call_id="CALL-1",
        session_id="SES-1",
        tool_name="invoice_reader",
        instruction_origin=InstructionOrigin.USER,
        original_user_intent="Summarize invoice",
    )
    assert call.timestamp is not None
