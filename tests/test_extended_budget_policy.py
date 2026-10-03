from copy import deepcopy

import pytest
from pydantic import ValidationError

from app.policy_config import (
    AegisPolicyConfig,
    load_policy_config,
)


def _raw_policy() -> dict:
    return (
        load_policy_config()
        .model_dump(
            mode="python"
        )
    )


def test_extended_budget_defaults_load() -> None:
    policy = (
        load_policy_config()
    )

    budgets = policy.budgets

    assert (
        budgets
        .max_agent_turns_per_session
        == 20
    )

    assert (
        budgets
        .max_input_tokens_per_session
        == 100_000
    )

    assert (
        budgets
        .max_output_tokens_per_session
        == 50_000
    )

    assert (
        budgets
        .max_execution_duration_ms_per_session
        == 300_000.0
    )

    assert (
        budgets
        .max_model_runtime_ms_per_session
        == 240_000.0
    )


@pytest.mark.parametrize(
    (
        "budget_field",
        "ceiling_field",
    ),
    [
        (
            "max_agent_turns_per_session",
            "maximum_agent_turns_per_session",
        ),
        (
            "max_input_tokens_per_session",
            "maximum_input_tokens_per_session",
        ),
        (
            "max_output_tokens_per_session",
            "maximum_output_tokens_per_session",
        ),
        (
            "max_execution_duration_ms_per_session",
            "maximum_execution_duration_ms_per_session",
        ),
        (
            "max_model_runtime_ms_per_session",
            "maximum_model_runtime_ms_per_session",
        ),
    ],
)
def test_extended_budget_cannot_exceed_organization_ceiling(
    budget_field: str,
    ceiling_field: str,
) -> None:
    raw = deepcopy(
        _raw_policy()
    )

    ceiling = (
        raw[
            "organization_ceilings"
        ][
            ceiling_field
        ]
    )

    raw[
        "budgets"
    ][
        budget_field
    ] = ceiling + 1

    with pytest.raises(
        ValidationError,
        match=(
            "organization ceiling"
        ),
    ):
        (
            AegisPolicyConfig
            .model_validate(
                raw
            )
        )


def test_extended_budget_can_be_lowered_safely() -> None:
    raw = deepcopy(
        _raw_policy()
    )

    raw[
        "budgets"
    ][
        "max_agent_turns_per_session"
    ] = 4

    raw[
        "budgets"
    ][
        "max_input_tokens_per_session"
    ] = 5000

    policy = (
        AegisPolicyConfig
        .model_validate(
            raw
        )
    )

    assert (
        policy
        .budgets
        .max_agent_turns_per_session
        == 4
    )

    assert (
        policy
        .budgets
        .max_input_tokens_per_session
        == 5000
    )