"""Tests for runtime performance and audit telemetry."""

import pytest
from fastapi.testclient import TestClient

from app.contracts import DecisionAction
from app.main import app
from app.telemetry import RuntimeTelemetry


client = TestClient(app)


def test_empty_telemetry_snapshot() -> None:
    telemetry = RuntimeTelemetry()

    snapshot = telemetry.snapshot()

    assert snapshot["evaluation_count"] == 0
    assert snapshot["executed_count"] == 0
    assert snapshot["prevented_count"] == 0
    assert snapshot["execution_rate"] == 0.0
    assert snapshot["prevention_rate"] == 0.0
    assert snapshot["latency_ms"]["average"] == 0.0
    assert snapshot["latency_ms"]["p95"] == 0.0


def test_telemetry_calculates_action_and_latency_metrics(
) -> None:
    telemetry = RuntimeTelemetry()

    telemetry.record(
        action=DecisionAction.ALLOW,
        executed=True,
        latency_ms=10.0,
    )
    telemetry.record(
        action=DecisionAction.BLOCK,
        executed=False,
        latency_ms=30.0,
    )

    snapshot = telemetry.snapshot()

    assert snapshot["evaluation_count"] == 2
    assert snapshot["action_counts"]["ALLOW"] == 1
    assert snapshot["action_counts"]["BLOCK"] == 1
    assert snapshot["executed_count"] == 1
    assert snapshot["prevented_count"] == 1
    assert snapshot["execution_rate"] == 0.5
    assert snapshot["prevention_rate"] == 0.5
    assert snapshot["latency_ms"]["average"] == 20.0
    assert snapshot["latency_ms"]["minimum"] == 10.0
    assert snapshot["latency_ms"]["maximum"] == 30.0
    assert snapshot["latency_ms"]["p95"] == 30.0


def test_telemetry_rejects_negative_latency() -> None:
    telemetry = RuntimeTelemetry()

    with pytest.raises(
        ValueError,
        match="latency_ms",
    ):
        telemetry.record(
            action=DecisionAction.ALLOW,
            executed=True,
            latency_ms=-1.0,
        )


def test_runtime_reset_clears_telemetry() -> None:
    client.post("/runtime/reset")

    response = client.post(
        "/gateway/evaluate",
        json={
            "call": {
                "call_id": "TELEMETRY-TEST-001",
                "session_id": "TELEMETRY-TEST-SESSION",
                "tool_name": "summarizer",
                "arguments": {
                    "content": (
                        "Invoice contains approved items."
                    )
                },
                "instruction_origin": "USER",
                "original_user_intent": (
                    "Summarize this invoice internally."
                ),
            },
            "input_artifacts": [],
            "estimated_cost": 0.001,
        },
    )

    assert response.status_code == 200

    before_reset = client.get(
        "/telemetry"
    ).json()

    assert (
        before_reset["metrics"][
            "evaluation_count"
        ]
        == 1
    )
    assert (
        before_reset["audit"][
            "decision_count"
        ]
        == 1
    )

    reset_response = client.post(
        "/runtime/reset"
    )

    assert reset_response.status_code == 200

    after_reset = client.get(
        "/telemetry"
    ).json()

    assert (
        after_reset["metrics"][
            "evaluation_count"
        ]
        == 0
    )
    assert (
        after_reset["audit"][
            "decision_count"
        ]
        == 0
    )
    assert (
        after_reset["audit"][
            "receipt_count"
        ]
        == 0
    )