import pytest

from app.contracts import (
    DataArtifact,
    DecisionAction,
    Guardrail,
    InstructionOrigin,
    ToolCall,
)
from app.controls.policy import PolicyEngine
from app.gateway.service import Gateway
from app.security.redaction import (
    REDACTED_VALUE,
    redact_artifacts,
)


def _customer_artifact() -> DataArtifact:
    return DataArtifact(
        artifact_id="artifact-sensitive-001",
        value={
            "name": "John Smith",
            "email": "john@example.com",
            "notes": (
                "Contact john@example.com "
                "about the account."
            ),
        },
        labels={"CustomerPII"},
        transformation="database_read",
    )


def _redaction_call() -> ToolCall:
    return ToolCall(
        call_id="CALL-REDACT-001",
        session_id="SESSION-REDACT-001",
        tool_name="external_http",
        arguments={},
        instruction_origin=(
            InstructionOrigin.USER
        ),
        original_user_intent=(
            "Send a sanitized customer summary."
        ),
    )


def _redaction_gateway() -> Gateway:
    guardrail = Guardrail(
        guardrail_id="GR-REDACT-001",
        source_labels={"CustomerPII"},
        destination="EXTERNAL",
        action=DecisionAction.REDACT,
        generated_from_attack=(
            "TEST-REDACTION"
        ),
        reason=(
            "Customer PII must be redacted "
            "before this controlled transfer."
        ),
    )

    policy_engine = PolicyEngine(
        [guardrail]
    )

    return Gateway(
        policy_engine,
        enforce_semantic=False,
        enforce_composition=False,
    )


def test_redactor_replaces_email_and_sensitive_key() -> None:
    artifact = _customer_artifact()

    result = redact_artifacts(
        [artifact]
    )

    assert result.changed is True

    assert result.changed_artifact_count == 1

    assert (
        result.redacted_value_count
        >= 2
    )

    sanitized = result.artifacts[0]

    assert sanitized.artifact_id == (
        "redacted-artifact-sensitive-001"
    )

    assert (
        sanitized.value["email"]
        == REDACTED_VALUE
    )

    assert (
        "john@example.com"
        not in sanitized.value["notes"]
    )

    assert (
        REDACTED_VALUE
        in sanitized.value["notes"]
    )

    assert "CustomerPII" not in (
        sanitized.labels
    )

    assert "REDACTED" in (
        sanitized.labels
    )

    assert (
        sanitized.parent_artifact_ids
        == ["artifact-sensitive-001"]
    )

    assert (
        sanitized.transformation
        == "redact"
    )


def test_redactor_does_not_mutate_original_artifact() -> None:
    artifact = _customer_artifact()

    original_value = {
        "name": "John Smith",
        "email": "john@example.com",
        "notes": (
            "Contact john@example.com "
            "about the account."
        ),
    }

    result = redact_artifacts(
        [artifact]
    )

    assert result.changed is True

    assert artifact.value == original_value

    assert (
        artifact.labels
        == {"CustomerPII"}
    )


@pytest.mark.asyncio
async def test_gateway_executes_after_redaction() -> None:
    gateway = _redaction_gateway()

    decision, receipt = await gateway.process(
        _redaction_call(),
        [_customer_artifact()],
    )

    assert (
        decision.action
        == DecisionAction.REDACT
    )

    assert receipt is not None

    assert receipt.succeeded is True

    assert (
        "Policy required redaction"
        in decision.reason
    )

    assert (
        receipt.input_artifact_ids
        == [
            "redacted-artifact-sensitive-001"
        ]
    )

    redaction_effects = [
        effect
        for effect
        in receipt.observed_effects
        if effect.effect_type
        == "REDACTION"
    ]

    assert len(redaction_effects) == 1

    effect = redaction_effects[0]

    assert (
        effect.metadata[
            "redacted_value_count"
        ]
        >= 2
    )

    assert (
        effect.metadata[
            "changed_artifact_count"
        ]
        == 1
    )

    assert (
        effect.metadata[
            "original_artifact_ids"
        ]
        == [
            "artifact-sensitive-001"
        ]
    )

    assert (
        effect.metadata[
            "sanitized_artifact_ids"
        ]
        == [
            "redacted-artifact-sensitive-001"
        ]
    )


@pytest.mark.asyncio
async def test_external_effect_contains_no_sensitive_label_after_redaction() -> None:
    gateway = _redaction_gateway()

    decision, receipt = await gateway.process(
        _redaction_call(),
        [_customer_artifact()],
    )

    assert (
        decision.action
        == DecisionAction.REDACT
    )

    assert receipt is not None

    external_effects = [
        effect
        for effect
        in receipt.observed_effects
        if effect.effect_type
        == "EXTERNAL_NETWORK"
    ]

    assert len(external_effects) == 1

    external_effect = external_effects[0]

    assert (
        "CustomerPII"
        not in external_effect.data_labels
    )

    assert (
        "Credential"
        not in external_effect.data_labels
    )

    assert (
        "Secret"
        not in external_effect.data_labels
    )

    assert (
        "REDACTED"
        in external_effect.data_labels
    )


@pytest.mark.asyncio
async def test_redaction_fails_closed_when_nothing_can_be_redacted() -> None:
    gateway = _redaction_gateway()

    artifact = DataArtifact(
        artifact_id="artifact-sensitive-empty",
        value={
            "name": "John Smith",
            "status": "active",
        },
        labels={"CustomerPII"},
    )

    decision, receipt = await gateway.process(
        _redaction_call(),
        [artifact],
    )

    assert (
        decision.action
        == DecisionAction.BLOCK
    )

    assert receipt is None

    assert (
        "no redactable sensitive value"
        in decision.reason.lower()
    )


@pytest.mark.asyncio
async def test_existing_block_action_still_blocks() -> None:
    guardrail = Guardrail(
        guardrail_id="GR-BLOCK-001",
        source_labels={"CustomerPII"},
        destination="EXTERNAL",
        action=DecisionAction.BLOCK,
        generated_from_attack=(
            "TEST-BLOCK"
        ),
        reason="Sensitive transfer blocked.",
    )

    gateway = Gateway(
        PolicyEngine([guardrail]),
        enforce_semantic=False,
        enforce_composition=False,
    )

    decision, receipt = await gateway.process(
        _redaction_call(),
        [_customer_artifact()],
    )

    assert (
        decision.action
        == DecisionAction.BLOCK
    )

    assert receipt is None