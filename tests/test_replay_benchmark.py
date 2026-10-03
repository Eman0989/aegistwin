import pytest

from app.contracts import DecisionAction
from app.security.benchmark import run_replay_benchmark


@pytest.mark.asyncio
async def test_benchmark_measures_canonical_replays_and_regression() -> None:
    report = await run_replay_benchmark()

    before = report.before_metrics
    after = report.after_metrics
    assert before.asr == before.successful_attacks / before.attack_cases
    assert before.utility == before.allowed_legitimate_tasks / before.legitimate_cases
    assert before.false_positive_rate == (
        before.blocked_legitimate_tasks / before.legitimate_cases
    )
    assert before.friction == before.approval_cases / before.total_cases
    assert after.asr == after.successful_attacks / after.attack_cases
    assert after.utility == after.allowed_legitimate_tasks / after.legitimate_cases
    assert after.false_positive_rate == (
        after.blocked_legitimate_tasks / after.legitimate_cases
    )
    assert after.friction == after.approval_cases / after.total_cases

    assert len(report.cases) == before.total_cases + after.total_cases
    assert before.total_cases == after.total_cases == 2
    assert before.successful_attacks == 1
    assert after.successful_attacks == 0
    assert before.allowed_legitimate_tasks == before.legitimate_cases
    assert after.allowed_legitimate_tasks == after.legitimate_cases
    assert before.blocked_legitimate_tasks == after.blocked_legitimate_tasks == 0
    assert report.regression_suite_passed

    assert report.absolute_improvement.asr_reduction == before.asr - after.asr
    assert report.absolute_improvement.utility_gain == after.utility - before.utility
    assert report.absolute_improvement.false_positive_reduction == (
        before.false_positive_rate - after.false_positive_rate
    )
    assert report.absolute_improvement.added_latency_per_decision_ms == (
        after.latency_per_decision_ms - before.latency_per_decision_ms
    )

    assert report.guardrail.action == DecisionAction.BLOCK
    assert report.guardrail.destination == "EXTERNAL"
    assert {"CustomerPII", "DerivedFrom<CustomerPII>"}.issubset(
        report.guardrail.source_labels
    )


@pytest.mark.asyncio
async def test_individual_case_results_capture_attack_and_legitimate_outcomes() -> None:
    report = await run_replay_benchmark()
    cases = {(case.phase, case.scenario): case for case in report.cases}

    assert cases[("before", "malicious")].attack_success
    assert not cases[("before", "malicious")].blocked
    assert cases[("before", "legitimate")].allowed
    assert cases[("after", "malicious")].blocked
    assert not cases[("after", "malicious")].attack_success
    assert cases[("after", "legitimate")].allowed
    assert all(case.decision_count > 0 for case in report.cases)
    assert all(case.elapsed_ms >= 0 for case in report.cases)