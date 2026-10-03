"""Centralized, validated AegisTwin policy configuration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from app.contracts import DecisionAction


DEFAULT_POLICY_PATH = (
    Path(__file__).resolve().parents[1]
    / "policies"
    / "aegis.yaml"
)


class ControlSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_allow_list: bool = True
    semantic_detection: bool = True
    composition_analysis: bool = True
    deterministic_policy: bool = True
    data_lineage: bool = True
    human_approval: bool = True
    budget_enforcement: bool = True
    historical_attack_detection: bool = True


class ToolSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    allowed: set[str] = Field(
        min_length=1
    )


class ModelSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    allowed: set[str] = Field(
        min_length=1
    )
    semantic_threshold: float = Field(
        default=0.80,
        ge=0.0,
        le=1.0,
    )


class DataSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sensitive_labels: set[str] = Field(
        min_length=1
    )
    external_destinations: set[str] = Field(
        min_length=1
    )


class BudgetSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_tool_calls_per_session: int = Field(
        default=100,
        ge=0,
    )
    max_external_http_calls_per_session: int = Field(
        default=10,
        ge=0,
    )
    max_estimated_cost_per_session: float = Field(
        default=100.0,
        ge=0.0,
    )


class ActionSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sensitive_external_data: DecisionAction = (
        DecisionAction.BLOCK
    )
    unknown_tool: DecisionAction = (
        DecisionAction.BLOCK
    )
    unknown_model: DecisionAction = (
        DecisionAction.BLOCK
    )
    historical_exploit: DecisionAction = (
        DecisionAction.BLOCK
    )


class OrganizationCeilings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    permanently_blocked_data_labels: set[str] = (
        Field(min_length=1)
    )
    permanently_blocked_destinations: set[str] = (
        Field(min_length=1)
    )
    maximum_tool_calls_per_session: int = Field(
        default=1000,
        ge=0,
    )
    maximum_external_http_calls_per_session: int = Field(
        default=100,
        ge=0,
    )
    maximum_estimated_cost_per_session: float = Field(
        default=1000.0,
        ge=0.0,
    )


class AegisPolicyConfig(BaseModel):
    """Validated policy with non-overridable ceilings."""

    model_config = ConfigDict(extra="forbid")

    version: str
    controls: ControlSettings
    tools: ToolSettings
    models: ModelSettings
    data: DataSettings
    budgets: BudgetSettings
    actions: ActionSettings
    historical_attack_signatures: set[str] = (
        Field(default_factory=set)
    )
    organization_ceilings: OrganizationCeilings

    @model_validator(mode="after")
    def validate_organization_ceilings(
        self,
    ) -> "AegisPolicyConfig":
        ceilings = self.organization_ceilings
        budgets = self.budgets

        if (
            budgets.max_tool_calls_per_session
            > ceilings.maximum_tool_calls_per_session
        ):
            raise ValueError(
                "Configured tool-call budget exceeds "
                "the organization ceiling."
            )

        if (
            budgets.max_external_http_calls_per_session
            > ceilings
            .maximum_external_http_calls_per_session
        ):
            raise ValueError(
                "Configured external-call budget exceeds "
                "the organization ceiling."
            )

        if (
            budgets.max_estimated_cost_per_session
            > ceilings.maximum_estimated_cost_per_session
        ):
            raise ValueError(
                "Configured cost budget exceeds "
                "the organization ceiling."
            )

        if not (
            ceilings.permanently_blocked_data_labels
            .issubset(self.data.sensitive_labels)
        ):
            raise ValueError(
                "Permanent sensitive labels cannot be "
                "removed from the active policy."
            )

        if not (
            ceilings.permanently_blocked_destinations
            .issubset(self.data.external_destinations)
        ):
            raise ValueError(
                "Permanent blocked destinations cannot "
                "be removed from the active policy."
            )

        if (
            self.actions.sensitive_external_data
            != DecisionAction.BLOCK
        ):
            raise ValueError(
                "Organization ceilings require sensitive "
                "external data to remain blocked."
            )

        if (
            self.actions.unknown_tool
            != DecisionAction.BLOCK
        ):
            raise ValueError(
                "Organization ceilings require unknown "
                "tools to remain blocked."
            )

        if (
            self.actions.unknown_model
            != DecisionAction.BLOCK
        ):
            raise ValueError(
                "Organization ceilings require unknown "
                "models to remain blocked."
            )

        return self

    def public_view(self) -> dict[str, Any]:
        """Return a frontend-safe policy representation."""

        return self.model_dump(
            mode="json"
        )


def load_policy_config(
    path: str | Path = DEFAULT_POLICY_PATH,
) -> AegisPolicyConfig:
    """Load and validate one centralized YAML policy."""

    policy_path = Path(path)

    if not policy_path.is_file():
        raise FileNotFoundError(
            f"Policy file not found: {policy_path}"
        )

    with policy_path.open(
        "r",
        encoding="utf-8",
    ) as policy_file:
        raw_config = yaml.safe_load(policy_file)

    if not isinstance(raw_config, dict):
        raise ValueError(
            "Policy file must contain a YAML object."
        )

    return AegisPolicyConfig.model_validate(
        raw_config
    )