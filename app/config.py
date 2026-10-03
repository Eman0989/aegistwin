"""Runtime configuration derived from the central policy file."""

from app.policy_config import (
    AegisPolicyConfig,
    load_policy_config,
)


ACTIVE_POLICY: AegisPolicyConfig = (
    load_policy_config()
)

SENSITIVE_LABELS = set(
    ACTIVE_POLICY.data.sensitive_labels
)

EXTERNAL_DESTINATIONS = set(
    ACTIVE_POLICY.data.external_destinations
)

EXTERNAL_DESTINATION = (
    sorted(EXTERNAL_DESTINATIONS)[0]
)

MVP_TOOLS = set(
    ACTIVE_POLICY.tools.allowed
)

ALLOWED_MODELS = set(
    ACTIVE_POLICY.models.allowed
)

SEMANTIC_THRESHOLD = (
    ACTIVE_POLICY.models.semantic_threshold
)

MAX_TOOL_CALLS = (
    ACTIVE_POLICY
    .budgets
    .max_tool_calls_per_session
)

MAX_EXTERNAL_HTTP_CALLS = (
    ACTIVE_POLICY
    .budgets
    .max_external_http_calls_per_session
)

MAX_ESTIMATED_COST = (
    ACTIVE_POLICY
    .budgets
    .max_estimated_cost_per_session
)

HISTORICAL_ATTACK_SIGNATURES = set(
    ACTIVE_POLICY.historical_attack_signatures
)

ORGANIZATION_CEILINGS = (
    ACTIVE_POLICY.organization_ceilings
)


def apply_policy_config(
    policy: AegisPolicyConfig,
) -> None:
    """Apply one already-validated policy to live runtime config.

    Mutable sets are updated in place so modules that imported the
    original set objects continue to observe the new configuration.
    """

    global ACTIVE_POLICY
    global EXTERNAL_DESTINATION
    global SEMANTIC_THRESHOLD
    global MAX_TOOL_CALLS
    global MAX_EXTERNAL_HTTP_CALLS
    global MAX_ESTIMATED_COST
    global ORGANIZATION_CEILINGS

    ACTIVE_POLICY = policy

    SENSITIVE_LABELS.clear()
    SENSITIVE_LABELS.update(
        policy.data.sensitive_labels
    )

    EXTERNAL_DESTINATIONS.clear()
    EXTERNAL_DESTINATIONS.update(
        policy.data.external_destinations
    )

    EXTERNAL_DESTINATION = (
        sorted(EXTERNAL_DESTINATIONS)[0]
    )

    MVP_TOOLS.clear()
    MVP_TOOLS.update(
        policy.tools.allowed
    )

    ALLOWED_MODELS.clear()
    ALLOWED_MODELS.update(
        policy.models.allowed
    )

    HISTORICAL_ATTACK_SIGNATURES.clear()
    HISTORICAL_ATTACK_SIGNATURES.update(
        policy.historical_attack_signatures
    )

    SEMANTIC_THRESHOLD = (
        policy.models.semantic_threshold
    )

    MAX_TOOL_CALLS = (
        policy
        .budgets
        .max_tool_calls_per_session
    )

    MAX_EXTERNAL_HTTP_CALLS = (
        policy
        .budgets
        .max_external_http_calls_per_session
    )

    MAX_ESTIMATED_COST = (
        policy
        .budgets
        .max_estimated_cost_per_session
    )

    ORGANIZATION_CEILINGS = (
        policy.organization_ceilings
    )