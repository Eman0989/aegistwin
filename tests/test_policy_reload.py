from copy import deepcopy
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

import app.config as runtime_config
import app.main as main_module
from app.main import app
from app.policy_config import (
    DEFAULT_POLICY_PATH,
    load_policy_config,
)


client = TestClient(app)


def _raw_default_policy() -> dict:
    with DEFAULT_POLICY_PATH.open(
        "r",
        encoding="utf-8",
    ) as policy_file:
        raw = yaml.safe_load(
            policy_file
        )

    assert isinstance(
        raw,
        dict,
    )

    return raw


def _write_policy(
    path: Path,
    raw: dict,
) -> None:
    with path.open(
        "w",
        encoding="utf-8",
    ) as policy_file:
        yaml.safe_dump(
            raw,
            policy_file,
            sort_keys=False,
        )


def _legitimate_request(
    *,
    call_id: str,
    session_id: str,
    tool_name: str = "summarizer",
) -> dict:
    return {
        "call": {
            "call_id": call_id,
            "session_id": session_id,
            "tool_name": tool_name,
            "arguments": {
                "text": (
                    "Summarize this approved "
                    "internal report."
                )
            },
            "instruction_origin": "USER",
            "original_user_intent": (
                "Summarize an approved "
                "internal report."
            ),
        },
        "input_artifacts": [],
        "estimated_cost": 0.01,
    }


@pytest.fixture(
    autouse=True,
)
def restore_default_policy() -> None:
    client.post(
        "/runtime/reset"
    )

    yield

    main_module.POLICY_PATH = (
        DEFAULT_POLICY_PATH
    )

    main_module._apply_runtime_policy(
        load_policy_config()
    )

    client.post(
        "/runtime/reset"
    )


def test_policy_endpoint_reports_hot_reload() -> None:
    response = client.get(
        "/policy"
    )

    assert response.status_code == 200

    payload = response.json()

    assert (
        payload["hot_reload"]
        is True
    )

    assert (
        payload["reload_mode"]
        == "hot"
    )

    assert (
        "reload_count"
        in payload
    )

    assert (
        "last_reloaded_at"
        in payload
    )


def test_valid_reload_updates_runtime_controls(
    tmp_path: Path,
) -> None:
    raw = deepcopy(
        _raw_default_policy()
    )

    raw["version"] = (
        "hot-reload-test"
    )

    raw["controls"][
        "semantic_detection"
    ] = False

    raw["controls"][
        "composition_analysis"
    ] = False

    raw["models"][
        "semantic_threshold"
    ] = 0.91

    raw["budgets"][
        "max_tool_calls_per_session"
    ] = 7

    policy_path = (
        tmp_path
        / "hot-policy.yaml"
    )

    _write_policy(
        policy_path,
        raw,
    )

    main_module.POLICY_PATH = (
        policy_path
    )

    response = client.post(
        "/policy/reload"
    )

    assert response.status_code == 200

    payload = response.json()

    assert (
        payload["status"]
        == "reloaded"
    )

    assert (
        payload["policy_version"]
        == "hot-reload-test"
    )

    assert (
        payload[
            "semantic_threshold"
        ]
        == 0.91
    )

    assert (
        payload["controls"][
            "semantic_detection"
        ]
        is False
    )

    assert (
        payload["budgets"][
            "max_tool_calls_per_session"
        ]
        == 7
    )

    capabilities = client.get(
        "/capabilities"
    ).json()

    assert (
        capabilities[
            "policy_version"
        ]
        == "hot-reload-test"
    )

    assert (
        capabilities["controls"][
            "semantic_injection_detection"
        ]["enabled"]
        is False
    )

    assert (
        capabilities["controls"][
            "semantic_injection_detection"
        ]["threshold"]
        == 0.91
    )

    assert (
        capabilities["controls"][
            "budget_enforcement"
        ][
            "max_tool_calls_per_session"
        ]
        == 7
    )


def test_reload_changes_tool_allow_list_immediately(
    tmp_path: Path,
) -> None:
    before = client.post(
        "/gateway/evaluate",
        json=_legitimate_request(
            call_id=(
                "CALL-RELOAD-BEFORE"
            ),
            session_id=(
                "SESSION-RELOAD-BEFORE"
            ),
        ),
    )

    assert (
        before.status_code
        == 200
    )

    assert (
        before.json()[
            "decision"
        ]["action"]
        == "ALLOW"
    )

    raw = deepcopy(
        _raw_default_policy()
    )

    raw["version"] = (
        "remove-summarizer"
    )

    raw["tools"]["allowed"].remove(
        "summarizer"
    )

    policy_path = (
        tmp_path
        / "remove-tool.yaml"
    )

    _write_policy(
        policy_path,
        raw,
    )

    main_module.POLICY_PATH = (
        policy_path
    )

    reload_response = client.post(
        "/policy/reload"
    )

    assert (
        reload_response.status_code
        == 200
    )

    after = client.post(
        "/gateway/evaluate",
        json=_legitimate_request(
            call_id=(
                "CALL-RELOAD-AFTER"
            ),
            session_id=(
                "SESSION-RELOAD-AFTER"
            ),
        ),
    )

    assert (
        after.status_code
        == 200
    )

    payload = after.json()

    assert (
        payload["decision"][
            "action"
        ]
        == "BLOCK"
    )

    assert (
        "Unsupported tool"
        in payload[
            "decision"
        ]["reason"]
    )


def test_budget_usage_survives_reload(
    tmp_path: Path,
) -> None:
    session_id = (
        "SESSION-BUDGET-RELOAD"
    )

    first = client.post(
        "/gateway/evaluate",
        json=_legitimate_request(
            call_id=(
                "CALL-BUDGET-FIRST"
            ),
            session_id=(
                session_id
            ),
        ),
    )

    assert (
        first.status_code
        == 200
    )

    assert (
        first.json()[
            "executed"
        ]
        is True
    )

    usage_before = (
        main_module
        .budget_manager
        .snapshot(
            session_id
        )
    )

    assert (
        usage_before.tool_calls
        == 1
    )

    raw = deepcopy(
        _raw_default_policy()
    )

    raw["version"] = (
        "budget-one"
    )

    raw["budgets"][
        "max_tool_calls_per_session"
    ] = 1

    policy_path = (
        tmp_path
        / "budget-one.yaml"
    )

    _write_policy(
        policy_path,
        raw,
    )

    main_module.POLICY_PATH = (
        policy_path
    )

    response = client.post(
        "/policy/reload"
    )

    assert (
        response.status_code
        == 200
    )

    usage_after = (
        main_module
        .budget_manager
        .snapshot(
            session_id
        )
    )

    assert (
        usage_after.tool_calls
        == 1
    )

    second = client.post(
        "/gateway/evaluate",
        json=_legitimate_request(
            call_id=(
                "CALL-BUDGET-SECOND"
            ),
            session_id=(
                session_id
            ),
        ),
    )

    assert (
        second.status_code
        == 200
    )

    payload = second.json()

    assert (
        payload["decision"][
            "action"
        ]
        == "BLOCK"
    )

    assert (
        "Maximum tool calls"
        in payload[
            "decision"
        ]["reason"]
    )


def test_invalid_reload_keeps_previous_policy(
    tmp_path: Path,
) -> None:
    previous_version = (
        runtime_config
        .ACTIVE_POLICY
        .version
    )

    previous_tools = set(
        runtime_config.MVP_TOOLS
    )

    raw = deepcopy(
        _raw_default_policy()
    )

    raw["version"] = (
        "invalid-policy"
    )

    raw["actions"][
        "sensitive_external_data"
    ] = "ALLOW"

    policy_path = (
        tmp_path
        / "invalid-policy.yaml"
    )

    _write_policy(
        policy_path,
        raw,
    )

    main_module.POLICY_PATH = (
        policy_path
    )

    response = client.post(
        "/policy/reload"
    )

    assert (
        response.status_code
        == 400
    )

    assert (
        runtime_config
        .ACTIVE_POLICY
        .version
        == previous_version
    )

    assert (
        runtime_config.MVP_TOOLS
        == previous_tools
    )

    assert (
        "active policy was not changed"
        in response.json()[
            "detail"
        ]
    )


def test_malformed_yaml_reload_is_rejected(
    tmp_path: Path,
) -> None:
    previous_version = (
        runtime_config
        .ACTIVE_POLICY
        .version
    )

    policy_path = (
        tmp_path
        / "broken.yaml"
    )

    policy_path.write_text(
        (
            "version: [broken\n"
            "controls:\n"
            "  tool_allow_list: true\n"
        ),
        encoding="utf-8",
    )

    main_module.POLICY_PATH = (
        policy_path
    )

    response = client.post(
        "/policy/reload"
    )

    assert (
        response.status_code
        == 400
    )

    assert (
        runtime_config
        .ACTIVE_POLICY
        .version
        == previous_version
    )