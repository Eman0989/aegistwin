import pytest

from app.controls.budget import BudgetManager, BudgetUsage


def test_budget_tracks_usage_separately_per_session() -> None:
    budget = BudgetManager(max_tool_calls=3, max_external_http_calls=1, max_estimated_cost=2.0)

    assert budget.consume("SES-1", "invoice_reader", 0.5).allowed
    assert budget.consume("SES-2", "external_http", 1.0).allowed

    assert budget.snapshot("SES-1") == BudgetUsage(tool_calls=1, estimated_cost=0.5)
    assert budget.snapshot("SES-2") == BudgetUsage(
        tool_calls=1, external_http_calls=1, estimated_cost=1.0
    )


def test_check_does_not_consume_and_consume_enforces_tool_call_limit() -> None:
    budget = BudgetManager(max_tool_calls=1)

    assert budget.check("SES-1", "invoice_reader").allowed
    assert budget.snapshot("SES-1") == BudgetUsage()
    assert budget.consume("SES-1", "invoice_reader").allowed
    result = budget.consume("SES-1", "invoice_reader")

    assert not result.allowed
    assert "tool calls" in result.reason
    assert budget.snapshot("SES-1").tool_calls == 1


def test_budget_enforces_external_http_limit_without_consuming_blocked_call() -> None:
    budget = BudgetManager(max_external_http_calls=1)
    budget.consume("SES-1", "external_http")

    result = budget.consume("SES-1", "external_http")

    assert not result.allowed
    assert "external HTTP calls" in result.reason
    assert budget.snapshot("SES-1").external_http_calls == 1


def test_budget_enforces_estimated_cost_without_consuming_blocked_call() -> None:
    budget = BudgetManager(max_estimated_cost=1.0)
    budget.consume("SES-1", "summarizer", 0.6)

    result = budget.consume("SES-1", "summarizer", 0.5)

    assert not result.allowed
    assert "estimated cost" in result.reason
    assert budget.snapshot("SES-1") == BudgetUsage(tool_calls=1, estimated_cost=0.6)


def test_budget_reset_supports_one_session_or_all_sessions() -> None:
    budget = BudgetManager()
    budget.consume("SES-1", "invoice_reader", 0.25)
    budget.consume("SES-2", "external_http", 0.5)

    budget.reset("SES-1")
    assert budget.snapshot("SES-1") == BudgetUsage()
    assert budget.snapshot("SES-2").tool_calls == 1

    budget.reset()
    assert budget.snapshot("SES-2") == BudgetUsage()


@pytest.mark.parametrize("estimated_cost", [-0.01, float("inf"), float("nan")])
def test_negative_or_non_finite_cost_is_rejected(estimated_cost: float) -> None:
    budget = BudgetManager()

    with pytest.raises(ValueError):
        budget.consume("SES-1", "invoice_reader", estimated_cost)


def test_negative_limits_are_rejected() -> None:
    with pytest.raises(ValueError, match="max_tool_calls"):
        BudgetManager(max_tool_calls=-1)

    with pytest.raises(ValueError, match="max_estimated_cost"):
        BudgetManager(max_estimated_cost=-1.0)