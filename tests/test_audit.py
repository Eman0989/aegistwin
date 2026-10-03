from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def _reset_runtime() -> None:
    response = client.post("/runtime/reset")
    assert response.status_code == 200


def _legitimate_request() -> dict:
    return {
        "call": {
            "call_id": "CALL-AUDIT-ALLOW-001",
            "session_id": "SESSION-AUDIT-ALLOW",
            "tool_name": "summarizer",
            "arguments": {
                "text": "Summarize this approved internal report."
            },
            "instruction_origin": "USER",
            "original_user_intent": (
                "Summarize an approved internal report."
            ),
        },
        "input_artifacts": [],
        "estimated_cost": 0.01,
    }


def _blocked_request() -> dict:
    return {
        "call": {
            "call_id": "CALL-AUDIT-BLOCK-001",
            "session_id": "SESSION-AUDIT-BLOCK",
            "tool_name": "shell_executor",
            "arguments": {
                "command": "echo test"
            },
            "instruction_origin": "USER",
            "original_user_intent": (
                "Run an unsupported shell tool."
            ),
        },
        "input_artifacts": [],
        "estimated_cost": 0.0,
    }


def test_audit_events_empty_after_reset() -> None:
    _reset_runtime()

    response = client.get("/audit/events")

    assert response.status_code == 200

    payload = response.json()

    assert payload["status"] == "ok"
    assert payload["event_count"] == 0
    assert payload["events"] == []
    assert "policy_version" in payload


def test_allowed_gateway_call_creates_audit_event() -> None:
    _reset_runtime()

    gateway_response = client.post(
        "/gateway/evaluate",
        json=_legitimate_request(),
    )

    assert gateway_response.status_code == 200

    gateway_payload = gateway_response.json()

    assert gateway_payload["decision"]["action"] == "ALLOW"
    assert gateway_payload["executed"] is True
    assert gateway_payload["receipt"] is not None

    audit_response = client.get("/audit/events")

    assert audit_response.status_code == 200

    payload = audit_response.json()

    assert payload["event_count"] == 1

    event = payload["events"][0]

    assert event["session_id"] == "SESSION-AUDIT-ALLOW"
    assert event["call_id"] == "CALL-AUDIT-ALLOW-001"
    assert event["tool_name"] == "summarizer"
    assert event["instruction_origin"] == "USER"
    assert event["action"] == "ALLOW"
    assert event["executed"] is True
    assert event["control"] == "execution"

    assert event["decision_id"].startswith("DEC-")
    assert event["receipt_id"].startswith("RCP-")

    assert event["risk"] == "LOW"
    assert event["latency_ms"] >= 0
    assert event["timestamp"]
    assert event["policy_version"]


def test_blocked_gateway_call_creates_audit_event() -> None:
    _reset_runtime()

    gateway_response = client.post(
        "/gateway/evaluate",
        json=_blocked_request(),
    )

    assert gateway_response.status_code == 200

    gateway_payload = gateway_response.json()

    assert gateway_payload["decision"]["action"] == "BLOCK"
    assert gateway_payload["executed"] is False
    assert gateway_payload["receipt"] is None

    audit_response = client.get("/audit/events")

    assert audit_response.status_code == 200

    payload = audit_response.json()

    assert payload["event_count"] == 1

    event = payload["events"][0]

    assert event["session_id"] == "SESSION-AUDIT-BLOCK"
    assert event["call_id"] == "CALL-AUDIT-BLOCK-001"
    assert event["tool_name"] == "shell_executor"

    assert event["action"] == "BLOCK"
    assert event["executed"] is False
    assert event["control"] == "tool_allow_list"

    assert event["risk"] == "HIGH"
    assert event["receipt_id"] is None
    assert "Unsupported tool" in event["reason"]


def test_audit_json_export_contains_events() -> None:
    _reset_runtime()

    gateway_response = client.post(
        "/gateway/evaluate",
        json=_blocked_request(),
    )

    assert gateway_response.status_code == 200

    response = client.get(
        "/audit/export",
        params={"format": "json"},
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["status"] == "ok"
    assert payload["format"] == "json"
    assert payload["event_count"] == 1

    event = payload["events"][0]

    assert event["call_id"] == "CALL-AUDIT-BLOCK-001"
    assert event["action"] == "BLOCK"
    assert event["control"] == "tool_allow_list"


def test_audit_csv_export_contains_expected_columns() -> None:
    _reset_runtime()

    gateway_response = client.post(
        "/gateway/evaluate",
        json=_legitimate_request(),
    )

    assert gateway_response.status_code == 200

    response = client.get(
        "/audit/export",
        params={"format": "csv"},
    )

    assert response.status_code == 200
    assert response.headers[
        "content-type"
    ].startswith("text/csv")

    csv_text = response.text

    assert "timestamp" in csv_text
    assert "session_id" in csv_text
    assert "call_id" in csv_text
    assert "tool_name" in csv_text
    assert "instruction_origin" in csv_text
    assert "control" in csv_text
    assert "action" in csv_text
    assert "reason" in csv_text
    assert "risk" in csv_text
    assert "latency_ms" in csv_text
    assert "executed" in csv_text
    assert "decision_id" in csv_text
    assert "receipt_id" in csv_text
    assert "policy_version" in csv_text

    assert "CALL-AUDIT-ALLOW-001" in csv_text
    assert "SESSION-AUDIT-ALLOW" in csv_text
    assert "ALLOW" in csv_text


def test_invalid_audit_export_format_is_rejected() -> None:
    _reset_runtime()

    response = client.get(
        "/audit/export",
        params={"format": "xml"},
    )

    assert response.status_code == 400

    payload = response.json()

    assert (
        payload["detail"]
        == (
            "Unsupported audit export format. "
            "Use 'json' or 'csv'."
        )
    )


def test_runtime_reset_clears_audit_events() -> None:
    _reset_runtime()

    gateway_response = client.post(
        "/gateway/evaluate",
        json=_legitimate_request(),
    )

    assert gateway_response.status_code == 200

    before_reset = client.get("/audit/events")

    assert before_reset.status_code == 200
    assert before_reset.json()["event_count"] == 1

    reset_response = client.post("/runtime/reset")

    assert reset_response.status_code == 200

    after_reset = client.get("/audit/events")

    assert after_reset.status_code == 200

    payload = after_reset.json()

    assert payload["event_count"] == 0
    assert payload["events"] == []