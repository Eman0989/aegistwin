from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_policy_endpoint_exposes_validated_config() -> None:
    response = client.get("/policy")

    assert response.status_code == 200

    body = response.json()

    assert body["status"] == "validated"
    assert body["source"] == "policies/aegis.yaml"
    assert body["policy"]["version"] == "1.0"
    assert (
        "external_http"
        in body["policy"]["tools"]["allowed"]
    )
    assert (
        body["policy"]["models"]["semantic_threshold"]
        == 0.80
    )
    assert (
        body["enforcement"]["organization_ceilings"]
        == "non_overridable"
    )


def test_capabilities_reports_policy_source() -> None:
    response = client.get("/capabilities")

    assert response.status_code == 200

    body = response.json()

    assert body["policy_source"] == "policies/aegis.yaml"
    assert body["policy_version"] == "1.0"
    assert (
        body["controls"][
            "semantic_injection_detection"
        ]["threshold"]
        == 0.80
    )


def test_policy_endpoint_reports_hot_reload() -> None:
    response = client.get("/policy")

    assert response.status_code == 200

    body = response.json()

    assert body["reload_mode"] == "hot"
    assert body["hot_reload"] is True
    assert "reload_count" in body
    assert "last_reloaded_at" in body