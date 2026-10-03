"""AegisTwin Shared Contract v1.0.

This file is the only canonical schema boundary between runtime and Twin
Intelligence. Changes require agreement from both owners.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class InstructionOrigin(str, Enum):
    USER = "USER"
    SYSTEM = "SYSTEM"
    TRUSTED_INTERNAL = "TRUSTED_INTERNAL"
    WEB_UNTRUSTED = "WEB_UNTRUSTED"
    DOCUMENT_UNTRUSTED = "DOCUMENT_UNTRUSTED"
    EMAIL_UNTRUSTED = "EMAIL_UNTRUSTED"
    MCP_TOOL_OUTPUT = "MCP_TOOL_OUTPUT"
    EXTERNAL_API = "EXTERNAL_API"


class DecisionAction(str, Enum):
    ALLOW = "ALLOW"
    BLOCK = "BLOCK"
    REDACT = "REDACT"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"


class ToolCall(BaseModel):
    call_id: str
    session_id: str
    tool_name: str

    arguments: dict[
        str,
        Any,
    ] = Field(
        default_factory=dict
    )

    instruction_origin: InstructionOrigin
    original_user_intent: str

    model_name: str | None = Field(
        default=None,
        min_length=1,
    )

    timestamp: datetime = Field(
        default_factory=lambda: (
            datetime.now(
                timezone.utc
            )
        )
    )


class ObservedEffect(BaseModel):
    effect_type: str
    resource: str | None = None
    destination: str | None = None

    data_labels: set[
        str
    ] = Field(
        default_factory=set
    )

    metadata: dict[
        str,
        Any,
    ] = Field(
        default_factory=dict
    )


class DataArtifact(BaseModel):
    artifact_id: str
    value: Any

    labels: set[
        str
    ] = Field(
        default_factory=set
    )

    parent_artifact_ids: list[
        str
    ] = Field(
        default_factory=list
    )

    transformation: str | None = None


class EffectReceipt(BaseModel):
    receipt_id: str
    call: ToolCall

    declared_effects: list[
        str
    ] = Field(
        default_factory=list
    )

    observed_effects: list[
        ObservedEffect
    ] = Field(
        default_factory=list
    )

    input_artifact_ids: list[
        str
    ] = Field(
        default_factory=list
    )

    output_artifacts: list[
        DataArtifact
    ] = Field(
        default_factory=list
    )

    tool_version: str = "1.0.0"
    tool_fingerprint: str | None = None
    succeeded: bool
    error: str | None = None


class ToolProfile(BaseModel):
    tool_name: str
    version: str

    declared_effects: set[
        str
    ] = Field(
        default_factory=set
    )

    observed_effects: set[
        str
    ] = Field(
        default_factory=set
    )

    capabilities: set[
        str
    ] = Field(
        default_factory=set
    )

    risk_level: RiskLevel = (
        RiskLevel.LOW
    )

    behavioral_mismatch: bool = False
    fingerprint: str | None = None


class AttackPath(BaseModel):
    attack_id: str
    original_intent: str
    instruction_origin: InstructionOrigin
    path: list[str]
    final_effect: str

    source_labels: set[
        str
    ] = Field(
        default_factory=set
    )

    destination: str | None = None
    risk_level: RiskLevel
    reproducible: bool = True

    evidence_receipt_ids: list[
        str
    ] = Field(
        default_factory=list
    )


class Guardrail(BaseModel):
    guardrail_id: str
    source_labels: set[str]
    destination: str

    action: DecisionAction = (
        DecisionAction.BLOCK
    )

    generated_from_attack: str
    reason: str
    enabled: bool = True


class PolicyDecision(BaseModel):
    decision_id: str
    call_id: str
    action: DecisionAction
    reason: str
    matched_guardrail_id: str | None = None

    risk_level: RiskLevel = (
        RiskLevel.LOW
    )


class TwinGraph(BaseModel):
    nodes: list[
        dict[str, Any]
    ]

    edges: list[
        dict[str, Any]
    ]


class WorkflowResult(BaseModel):
    workflow_name: str
    success: bool
    blocked: bool = False

    receipts: list[
        EffectReceipt
    ] = Field(
        default_factory=list
    )

    decisions: list[
        PolicyDecision
    ] = Field(
        default_factory=list
    )

    attack_path: AttackPath | None = None
    message: str