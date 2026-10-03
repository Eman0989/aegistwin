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