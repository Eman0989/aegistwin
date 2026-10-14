from unittest.mock import Mock, patch
from app.security.llm_response_inspector import (
    ResponseAction,
    inspect_response,
)


def test_allows_normal_response():
    result = inspect_response("Hello, how can I help?")

    assert result.action == ResponseAction.ALLOW
    assert result.content == "Hello, how can I help?"


def test_redacts_email_address():
    result = inspect_response(
        "Contact me at example@company.com."
    )

    assert result.action == ResponseAction.REDACT
    assert result.content == "Contact me at [REDACTED]."
    assert "example@company.com" not in result.content


def test_blocks_invalid_content():
    result = inspect_response(None)

    assert result.action == ResponseAction.BLOCK
    assert result.content is None


def test_redacts_multiple_emails():
    result = inspect_response(
        "Contact a@test.com or b@test.com."
    )

    assert result.action == ResponseAction.REDACT
    assert result.content.count("[REDACTED]") == 2

from unittest.mock import Mock, patch


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

def test_redaction_preserves_original_response():
    original = "Email me at private@company.com"

    result = inspect_response(original)

    assert original == "Email me at private@company.com"
    assert result.action == ResponseAction.REDACT
    assert "private@company.com" not in result.content
    assert "[REDACTED]" in result.content
