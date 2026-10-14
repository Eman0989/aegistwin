
from unittest.mock import Mock, patch

from app.security.llm_response_inspector import (
    ResponseAction,
    inspect_response,
)


# ==========================================
# 1. NORMAL RESPONSE
# ==========================================

def test_allows_normal_response():
    original = "Hello, how can I help?"

    result = inspect_response(original)

    assert result.action == ResponseAction.ALLOW
    assert result.content == original
    assert result.matched_rules == ()
    assert result.redaction_count == 0


# ==========================================
# 2. SINGLE EMAIL REDACTION
# ==========================================

def test_redacts_email_address():
    result = inspect_response(
        "Contact me at example@company.com."
    )

    assert result.action == ResponseAction.REDACT
    assert result.content == "Contact me at [REDACTED]."
    assert "example@company.com" not in result.content

    assert result.matched_rules == ("email",)
    assert result.redaction_count == 1


# ==========================================
# 3. INVALID RESPONSE CONTENT
# ==========================================

def test_blocks_invalid_content():
    result = inspect_response(None)

    assert result.action == ResponseAction.BLOCK
    assert result.content is None
    assert result.redaction_count == 0


# ==========================================
# 4. MULTIPLE EMAIL REDACTIONS
# ==========================================

def test_redacts_multiple_emails():
    result = inspect_response(
        "Contact a@test.com or b@test.com."
    )

    assert result.action == ResponseAction.REDACT
    assert result.content.count("[REDACTED]") == 2

    assert result.matched_rules == ("email",)
    assert result.redaction_count == 2


# ==========================================
# 5. REDACTOR RAISES VALUEERROR
# ==========================================

def test_blocks_when_redactor_raises_error():
    with patch(
        "app.security.llm_response_inspector.redact_artifacts",
        side_effect=ValueError("Redaction failed"),
    ):
        result = inspect_response(
            "Contact example@company.com"
        )

    assert result.action == ResponseAction.BLOCK
    assert result.content is None


# ==========================================
# 6. REDACTOR RETURNS INVALID CONTENT
# ==========================================

def test_blocks_when_redactor_returns_invalid_output():
    fake_result = Mock()
    fake_result.changed = True
    fake_result.artifacts = [Mock(value=None)]

    with patch(
        "app.security.llm_response_inspector.redact_artifacts",
        return_value=fake_result,
    ):
        result = inspect_response(
            "Contact example@company.com"
        )

    assert result.action == ResponseAction.BLOCK
    assert result.content is None


# ==========================================
# 7. ORIGINAL RESPONSE PRESERVED
# ==========================================

def test_redaction_preserves_original_response():
    original = "Email me at private@company.com"

    result = inspect_response(original)

    assert original == "Email me at private@company.com"
    assert result.action == ResponseAction.REDACT
    assert "private@company.com" not in result.content
    assert "[REDACTED]" in result.content


# ==========================================
# 8. EMPTY ARTIFACT LIST - FAIL CLOSED
# ==========================================

def test_blocks_when_redactor_returns_empty_artifacts():
    fake_result = Mock()
    fake_result.changed = True
    fake_result.artifacts = []

    with patch(
        "app.security.llm_response_inspector.redact_artifacts",
        return_value=fake_result,
    ):
        result = inspect_response(
            "Contact example@company.com"
        )

    assert result.action == ResponseAction.BLOCK
    assert result.content is None


# ==========================================
# 9. TYPEERROR - FAIL CLOSED
# ==========================================

def test_blocks_when_redactor_raises_typeerror():
    with patch(
        "app.security.llm_response_inspector.redact_artifacts",
        side_effect=TypeError("Unexpected redactor input"),
    ):
        result = inspect_response(
            "Contact example@company.com"
        )

    assert result.action == ResponseAction.BLOCK
    assert result.content is None
    assert result.redaction_count == 0


# ==========================================
# 10. EMPTY STRING
# ==========================================

def test_allows_empty_string():
    result = inspect_response("")

    assert result.action == ResponseAction.ALLOW
    assert result.content == ""
    assert result.matched_rules == ()
    assert result.redaction_count == 0
