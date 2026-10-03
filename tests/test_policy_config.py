from copy import deepcopy
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from app.contracts import DecisionAction
from app.policy_config import (
    DEFAULT_POLICY_PATH,
    AegisPolicyConfig,
    load_policy_config,
)


def _default_raw_policy() -> dict:
    with DEFAULT_POLICY_PATH.open(
        "r",
        encoding="utf-8",
    ) as policy_file:
        loaded = yaml.safe_load(policy_file)

    assert isinstance(loaded, dict)
    return loaded


def test_default_policy_loads() -> None:
    policy = load_policy_config()

    assert policy.version == "1.0"
    assert "external_http" in policy.tools.allowed
    assert (
        policy.models.semantic_threshold
        == 0.80
    )
    assert (
        policy.actions.sensitive_external_data
        == DecisionAction.BLOCK
    )
    assert "Secret" in policy.data.sensitive_labels


def test_public_view_is_serializable() -> None:
    policy = load_policy_config()
    public = policy.public_view()

    assert public["version"] == "1.0"
    assert (
        "invoice_reader"
        in public["tools"]["allowed"]
    )
    assert (
        public["actions"][
            "sensitive_external_data"
        ]
        == "BLOCK"
    )


def test_unknown_configuration_field_is_rejected() -> None:
    raw = _default_raw_policy()
    raw["unexpected_setting"] = True

    with pytest.raises(ValidationError):
        AegisPolicyConfig.model_validate(raw)


def test_semantic_threshold_must_be_valid() -> None:
    raw = _default_raw_policy()
    raw["models"]["semantic_threshold"] = 1.5

    with pytest.raises(ValidationError):
        AegisPolicyConfig.model_validate(raw)


def test_budget_cannot_exceed_org_ceiling() -> None:
    raw = _default_raw_policy()
    raw["budgets"][
        "max_tool_calls_per_session"
    ] = 1001

    with pytest.raises(
        ValidationError,
        match="organization ceiling",
    ):
        AegisPolicyConfig.model_validate(raw)


def test_permanent_sensitive_label_cannot_be_removed() -> None:
    raw = _default_raw_policy()
    raw["data"]["sensitive_labels"].remove(
        "Secret"
    )

    with pytest.raises(
        ValidationError,
        match="cannot be removed",
    ):
        AegisPolicyConfig.model_validate(raw)


def test_sensitive_external_action_must_remain_blocked() -> None:
    raw = _default_raw_policy()
    raw["actions"][
        "sensitive_external_data"
    ] = "ALLOW"

    with pytest.raises(
        ValidationError,
        match="remain blocked",
    ):
        AegisPolicyConfig.model_validate(raw)


def test_policy_can_be_loaded_from_custom_path(
    tmp_path: Path,
) -> None:
    raw = deepcopy(_default_raw_policy())
    raw["version"] = "test-version"

    custom_policy = (
        tmp_path / "custom-policy.yaml"
    )

    with custom_policy.open(
        "w",
        encoding="utf-8",
    ) as policy_file:
        yaml.safe_dump(
            raw,
            policy_file,
            sort_keys=False,
        )

    loaded = load_policy_config(
        custom_policy
    )

    assert loaded.version == "test-version"


def test_missing_policy_file_is_rejected(
    tmp_path: Path,
) -> None:
    missing = tmp_path / "missing.yaml"

    with pytest.raises(FileNotFoundError):
        load_policy_config(missing)