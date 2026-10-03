import pytest
from fastapi.testclient import (
    TestClient,
)

from app.main import app


client = TestClient(app)


@pytest.fixture(
    autouse=True
)
def reset_runtime_state() -> None:
    client.post(
        "/runtime/reset"
    )

    yield

    client.post(
        "/runtime/reset"
    )


def test_health_reports_service_and_version() -> None:
    response = client.get(
        "/health"
    )

    assert (
        response.status_code
        == 200
    )

    assert response.json() == {
        "status": "ok",
        "service": "AegisTwin MVP",
        "version": "1.0.0",
        "contract": "v1.0",
    }


def test_attack_demo_returns_cases_calculated_benchmark_and_regression() -> None:
    response = client.post(
        "/attack-my-agent"
    )

    assert (
        response.status_code
        == 200
    )

    payload = response.json()

    assert (
        payload[
            "original_user_intent"
        ]
        == "Summarize this invoice"
    )

    assert (
        payload[
            "instruction_origin"
        ]
        == "WEB_UNTRUSTED"
    )

    assert {
        "CustomerPII",
        "DerivedFrom<CustomerPII>",
    }.issubset(
        payload[
            "sensitive_lineage"
        ]
    )

    assert (
        payload[
            "attack_path"
        ]
        == [
            "invoice_reader",
            "customer_database",
            "summarizer",
            "external_http",
        ]
    )

    assert (
        payload[
            "before"
        ]["blocked"]
        is False
    )

    assert (
        payload[
            "generated_guardrail"
        ]["destination"]
        == "EXTERNAL"
    )

    assert (
        payload[
            "generated_guardrail"
        ]["action"]
        == "BLOCK"
    )

    assert (
        payload[
            "after"
        ]["blocked"]
        is True
    )

    assert (
        payload[
            "after"
        ][
            "decisions"
        ][-1]["action"]
        == "BLOCK"
    )

    assert (
        payload[
            "legitimate_workflow"
        ]["success"]
        is True
    )

    assert (
        payload[
            "legitimate_workflow"
        ]["blocked"]
        is False
    )

    benchmark = payload[
        "benchmark_report"
    ]

    before = benchmark[
        "before_metrics"
    ]

    after = benchmark[
        "after_metrics"
    ]

    assert (
        payload["asr_before"]
        == (
            before[
                "successful_attacks"
            ]
            / before[
                "attack_cases"
            ]
        )
    )

    assert (
        payload["asr_after"]
        == (
            after[
                "successful_attacks"
            ]
            / after[
                "attack_cases"
            ]
        )
    )

    assert (
        payload[
            "utility_before"
        ]
        == (
            before[
                "allowed_legitimate_tasks"
            ]
            / before[
                "legitimate_cases"
            ]
        )
    )

    assert (
        payload[
            "utility_after"
        ]
        == (
            after[
                "allowed_legitimate_tasks"
            ]
            / after[
                "legitimate_cases"
            ]
        )
    )

    assert (
        payload[
            "false_positive_rate"
        ]["before"]
        == (
            before[
                "blocked_legitimate_tasks"
            ]
            / before[
                "legitimate_cases"
            ]
        )
    )

    assert (
        payload[
            "false_positive_rate"
        ]["after"]
        == (
            after[
                "blocked_legitimate_tasks"
            ]
            / after[
                "legitimate_cases"
            ]
        )
    )

    assert (
        payload[
            "friction"
        ]["before"]
        == (
            before[
                "approval_cases"
            ]
            / before[
                "total_cases"
            ]
        )
    )

    assert (
        payload[
            "friction"
        ]["after"]
        == (
            after[
                "approval_cases"
            ]
            / after[
                "total_cases"
            ]
        )
    )

    assert (
        payload[
            "measured_latency"
        ][
            "before_ms_per_decision"
        ]
        >= 0
    )

    assert (
        payload[
            "measured_latency"
        ][
            "after_ms_per_decision"
        ]
        >= 0
    )

    assert (
        payload[
            "regression_passed"
        ]
        is True
    )

    assert (
        benchmark[
            "regression_suite_passed"
        ]
        is True
    )

    assert (
        len(
            benchmark["cases"]
        )
        == 4
    )


def test_attack_demo_exposes_complete_twin_analysis() -> None:
    response = client.post(
        "/attack-my-agent"
    )

    assert (
        response.status_code
        == 200
    )

    payload = response.json()

    assert (
        "twin_analysis"
        in payload
    )

    twin = payload[
        "twin_analysis"
    ]

    assert set(
        twin.keys()
    ) == {
        "tool_profiles",
        "capability_map",
        "graph",
        "provenance",
        "intent_action",
        "lineage",
        "attack_paths",
        "least_privilege",
        "drift",
    }

    # --------------------------------------------------
    # TOOL MRI
    # --------------------------------------------------

    assert (
        len(
            twin[
                "tool_profiles"
            ]
        )
        == 4
    )

    tool_names = {
        profile[
            "tool_name"
        ]
        for profile
        in twin[
            "tool_profiles"
        ]
    }

    assert tool_names == {
        "invoice_reader",
        "customer_database",
        "summarizer",
        "external_http",
    }

    # --------------------------------------------------
    # CAPABILITY MAP
    # --------------------------------------------------

    capability_map = twin[
        "capability_map"
    ]

    assert (
        capability_map[
            "summary"
        ]["total_tools"]
        == 4
    )

    assert (
        len(
            capability_map[
                "tools"
            ]
        )
        == 4
    )

    # --------------------------------------------------
    # DIGITAL TWIN GRAPH
    # --------------------------------------------------

    graph = twin[
        "graph"
    ]

    assert graph[
        "nodes"
    ]

    assert graph[
        "edges"
    ]

    graph_node_ids = {
        node["id"]
        for node
        in graph[
            "nodes"
        ]
    }

    assert (
        "tool:invoice_reader"
        in graph_node_ids
    )

    assert (
        "tool:customer_database"
        in graph_node_ids
    )

    assert (
        "tool:summarizer"
        in graph_node_ids
    )

    assert (
        "tool:external_http"
        in graph_node_ids
    )

    # --------------------------------------------------
    # PROVENANCE
    # --------------------------------------------------

    provenance = twin[
        "provenance"
    ]

    assert (
        provenance[
            "chain"
        ][
            "effective_origin"
        ]
        == "WEB_UNTRUSTED"
    )

    assert (
        provenance[
            "chain"
        ][
            "contains_untrusted_content"
        ]
        is True
    )

    assert (
        provenance[
            "calls"
        ]
    )

    # --------------------------------------------------
    # INTENT VS ACTION
    # --------------------------------------------------

    intent_action = twin[
        "intent_action"
    ]

    assert (
        intent_action
    )

    external_mismatches = [
        analysis
        for analysis
        in intent_action
        if (
            analysis[
                "final_effect"
            ]
            == "EXTERNAL_TRANSFER"
        )
    ]

    assert (
        len(
            external_mismatches
        )
        == 1
    )

    mismatch = (
        external_mismatches[0]
    )

    assert (
        mismatch[
            "aligned"
        ]
        is False
    )

    assert (
        mismatch[
            "risk_level"
        ]
        == "CRITICAL"
    )

    assert (
        mismatch[
            "destination"
        ]
        == "EXTERNAL"
    )

    # --------------------------------------------------
    # DATA LINEAGE
    # --------------------------------------------------

    lineage = twin[
        "lineage"
    ]

    assert {
        "CustomerPII",
        "DerivedFrom<CustomerPII>",
    }.issubset(
        set(
            lineage[
                "sensitive_labels"
            ]
        )
    )

    assert (
        lineage[
            "sensitive_artifact_ids"
        ]
    )

    assert (
        lineage[
            "traces"
        ]
    )

    # --------------------------------------------------
    # ATTACK PATH DISCOVERY
    # --------------------------------------------------

    attack_paths = twin[
        "attack_paths"
    ]

    assert (
        len(
            attack_paths
        )
        >= 1
    )

    discovered_attack = (
        attack_paths[0]
    )

    assert (
        discovered_attack[
            "risk_level"
        ]
        == "CRITICAL"
    )

    assert (
        discovered_attack[
            "instruction_origin"
        ]
        == "WEB_UNTRUSTED"
    )

    assert (
        discovered_attack[
            "destination"
        ]
        == "EXTERNAL"
    )

    assert {
        "CustomerPII",
        "DerivedFrom<CustomerPII>",
    }.issubset(
        set(
            discovered_attack[
                "source_labels"
            ]
        )
    )

    # --------------------------------------------------
    # LEAST PRIVILEGE
    # --------------------------------------------------

    least_privilege = twin[
        "least_privilege"
    ]

    assert (
        least_privilege[
            "summary"
        ]["total_tools"]
        == 4
    )

    assert (
        least_privilege[
            "recommendations"
        ]
    )

    # --------------------------------------------------
    # DRIFT
    # --------------------------------------------------

    drift = twin[
        "drift"
    ]

    assert (
        drift[
            "available"
        ]
        is False
    )

    assert (
        drift["report"]
        is None
    )

    assert (
        "previous behavioral profile"
        in drift[
            "reason"
        ].lower()
    )


def test_runtime_status_exposes_store_and_budget_state() -> None:
    demo_response = (
        client.post(
            "/attack-my-agent"
        )
    )

    assert (
        demo_response.status_code
        == 200
    )

    response = client.get(
        "/runtime/status"
    )

    assert (
        response.status_code
        == 200
    )

    status = response.json()

    assert (
        status[
            "receipts"
        ]
        > 0
    )

    assert (
        status[
            "decisions"
        ]
        > 0
    )

    assert (
        status[
            "pending_approvals"
        ]
        == 0
    )

    assert status[
        "session_budgets"
    ]

    assert all(
        "tool_calls"
        in usage
        for usage
        in status[
            "session_budgets"
        ].values()
    )


def test_runtime_reset_clears_store_and_session_budgets() -> None:
    assert (
        client.post(
            "/attack-my-agent"
        ).status_code
        == 200
    )

    reset_response = (
        client.post(
            "/runtime/reset"
        )
    )

    status_response = (
        client.get(
            "/runtime/status"
        )
    )

    assert (
        reset_response.status_code
        == 200
    )

    assert (
        reset_response.json()[
            "status"
        ]
        == "ok"
    )

    assert (
        status_response.json()
        == {
            "receipts": 0,
            "decisions": 0,
            "pending_approvals": 0,
            "session_budgets": {},
        }
    )