"""HTTP-level tests for AegisTwin management RBAC."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.auth import (
    ADMIN_KEY_ENV,
    SECURITY_KEY_ENV,
    VIEWER_KEY_ENV,
)
from app.main import app


client = TestClient(app)


@pytest.fixture(
    autouse=True,
)
def real_management_auth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exercise the real auth path instead of test overrides."""

    app.dependency_overrides.clear()

    monkeypatch.setenv(
        VIEWER_KEY_ENV,
        "viewer-test-key",
    )

    monkeypatch.setenv(
        SECURITY_KEY_ENV,
        "security-test-key",
    )

    monkeypatch.setenv(
        ADMIN_KEY_ENV,
        "admin-test-key",
    )

    yield

    app.dependency_overrides.clear()


def _headers(
    key: str,
) -> dict[str, str]:
    return {
        "X-API-Key": key,
    }


def test_public_health_does_not_require_management_auth() -> None:
    response = client.get(
        "/health"
    )

    assert (
        response.status_code
        == 200
    )


def test_management_endpoint_without_key_returns_401() -> None:
    response = client.get(
        "/telemetry"
    )

    assert (
        response.status_code
        == 401
    )

    payload = response.json()

    assert (
        "valid management api key"
        in payload["detail"].lower()
    )


def test_management_endpoint_with_invalid_key_returns_401() -> None:
    response = client.get(
        "/runtime/status",
        headers=_headers(
            "invalid-key"
        ),
    )

    assert (
        response.status_code
        == 401
    )


def test_viewer_can_read_telemetry() -> None:
    response = client.get(
        "/telemetry",
        headers=_headers(
            "viewer-test-key"
        ),
    )

    assert (
        response.status_code
        == 200
    )

    payload = response.json()

    assert (
        payload["status"]
        == "ok"
    )


def test_viewer_can_read_runtime_status() -> None:
    response = client.get(
        "/runtime/status",
        headers=_headers(
            "viewer-test-key"
        ),
    )

    assert (
        response.status_code
        == 200
    )


def test_viewer_cannot_read_security_audit() -> None:
    response = client.get(
        "/audit/events",
        headers=_headers(
            "viewer-test-key"
        ),
    )

    assert (
        response.status_code
        == 403
    )

    payload = response.json()

    assert (
        "security"
        in payload["detail"].lower()
    )


def test_viewer_cannot_reset_runtime() -> None:
    response = client.post(
        "/runtime/reset",
        headers=_headers(
            "viewer-test-key"
        ),
    )

    assert (
        response.status_code
        == 403
    )

    payload = response.json()

    assert (
        "admin"
        in payload["detail"].lower()
    )


def test_security_role_inherits_viewer_access() -> None:
    response = client.get(
        "/telemetry",
        headers=_headers(
            "security-test-key"
        ),
    )

    assert (
        response.status_code
        == 200
    )


def test_security_role_can_read_audit_events() -> None:
    response = client.get(
        "/audit/events",
        headers=_headers(
            "security-test-key"
        ),
    )

    assert (
        response.status_code
        == 200
    )

    payload = response.json()

    assert (
        payload["status"]
        == "ok"
    )


def test_security_role_can_export_audit() -> None:
    response = client.get(
        "/audit/export",
        params={
            "format": "json",
        },
        headers=_headers(
            "security-test-key"
        ),
    )

    assert (
        response.status_code
        == 200
    )


def test_security_role_cannot_reset_runtime() -> None:
    response = client.post(
        "/runtime/reset",
        headers=_headers(
            "security-test-key"
        ),
    )

    assert (
        response.status_code
        == 403
    )


def test_admin_inherits_viewer_access() -> None:
    response = client.get(
        "/telemetry",
        headers=_headers(
            "admin-test-key"
        ),
    )

    assert (
        response.status_code
        == 200
    )


def test_admin_inherits_security_access() -> None:
    response = client.get(
        "/audit/events",
        headers=_headers(
            "admin-test-key"
        ),
    )

    assert (
        response.status_code
        == 200
    )


def test_admin_can_reset_runtime() -> None:
    response = client.post(
        "/runtime/reset",
        headers=_headers(
            "admin-test-key"
        ),
    )

    assert (
        response.status_code
        == 200
    )

    payload = response.json()

    assert (
        payload["status"]
        == "ok"
    )

    assert (
        payload["message"]
        == "Runtime state reset."
    )


def test_viewer_can_read_persistence_status() -> None:
    response = client.get(
        "/persistence/status",
        headers=_headers(
            "viewer-test-key"
        ),
    )

    assert (
        response.status_code
        == 200
    )


def test_missing_auth_does_not_block_gateway_execution() -> None:
    response = client.post(
        "/gateway/evaluate",
        json={
            "call": {
                "call_id": (
                    "CALL-RBAC-PUBLIC-001"
                ),
                "session_id": (
                    "SESSION-RBAC-PUBLIC"
                ),
                "tool_name": (
                    "summarizer"
                ),
                "arguments": {
                    "text": (
                        "Summarize this approved "
                        "internal report."
                    )
                },
                "instruction_origin": (
                    "USER"
                ),
                "original_user_intent": (
                    "Summarize an approved "
                    "internal report."
                ),
            },
            "input_artifacts": [],
            "estimated_cost": 0.01,
        },
    )

    assert (
        response.status_code
        == 200
    )