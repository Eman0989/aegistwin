from copy import deepcopy
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

import app.main as main_module
from app.main import app
from app.policy_config import (
    DEFAULT_POLICY_PATH,
    load_policy_config,
)


client = TestClient(app)


APPROVED_MODEL = "llama3.2:3b"

UNKNOWN_MODEL = (
    "unapproved/provider-model:999b"
)


def _request(
    *,
    call_id: str,
    session_id: str,
    model_name: str | None,
) -> dict:
    call = {
        "call_id": call_id,
        "session_id": session_id,
        "tool_name": "summarizer",
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
    }

    if model_name is not None:
        call["model_name"] = (
            model_name
        )

    return {
        "call": call,
        "input_artifacts": [],
        "estimated_cost": 0.01,
    }


def _raw_policy() -> dict:
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


@pytest.fixture(
    autouse=True,
)
def restore_runtime_policy() -> None:
    client.post(
        "/runtime/reset"
    )

    main_module.POLICY_PATH = (
        DEFAULT_POLICY_PATH
    )

    main_module._apply_runtime_policy(
        load_policy_config()
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


def test_approved_model_is_allowed() -> None:
    response = client.post(
        "/gateway/evaluate",
        json=_request(
            call_id=(
                "CALL-MODEL-ALLOW-001"
            ),
            session_id=(
                "SESSION-MODEL-ALLOW"
            ),
            model_name=(
                APPROVED_MODEL
            ),
        ),
    )

    assert response.status_code == 200

    payload = response.json()

    assert (
        payload["decision"]["action"]
        == "ALLOW"
    )

    assert (
        payload["executed"]
        is True
    )

    assert (
        payload["receipt"]
        is not None
    )

    assert (
        payload["receipt"]["call"][
            "model_name"
        ]
        == APPROVED_MODEL
    )


def test_unknown_model_is_blocked() -> None:
    response = client.post(
        "/gateway/evaluate",
        json=_request(
            call_id=(
                "CALL-MODEL-BLOCK-001"
            ),
            session_id=(
                "SESSION-MODEL-BLOCK"
            ),
            model_name=(
                UNKNOWN_MODEL
            ),
        ),
    )

    assert response.status_code == 200

    payload = response.json()

    assert (
        payload["decision"]["action"]
        == "BLOCK"
    )

    assert (
        payload["executed"]
        is False
    )

    assert (
        payload["receipt"]
        is None
    )

    assert (
        "Unapproved model"
        in payload["decision"]["reason"]
    )

    assert (
        UNKNOWN_MODEL
        in payload["decision"]["reason"]
    )


def test_missing_model_name_preserves_existing_clients() -> None:
    response = client.post(
        "/gateway/evaluate",
        json=_request(
            call_id=(
                "CALL-MODEL-LEGACY-001"
            ),
            session_id=(
                "SESSION-MODEL-LEGACY"
            ),
            model_name=None,
        ),
    )

    assert response.status_code == 200

    payload = response.json()

    assert (
        payload["decision"]["action"]
        == "ALLOW"
    )

    assert (
        payload["executed"]
        is True
    )


def test_removing_model_then_hot_reload_blocks_it(
    tmp_path: Path,
) -> None:
    before = client.post(
        "/gateway/evaluate",
        json=_request(
            call_id=(
                "CALL-MODEL-BEFORE-RELOAD"
            ),
            session_id=(
                "SESSION-MODEL-BEFORE"
            ),
            model_name=(
                APPROVED_MODEL
            ),
        ),
    )

    assert before.status_code == 200

    assert (
        before.json()[
            "decision"
        ]["action"]
        == "ALLOW"
    )

    raw = deepcopy(
        _raw_policy()
    )

    raw["version"] = (
        "model-removed-test"
    )

    raw["models"]["allowed"].remove(
        APPROVED_MODEL
    )

    modified_policy = (
        tmp_path
        / "model-removed.yaml"
    )

    _write_policy(
        modified_policy,
        raw,
    )

    main_module.POLICY_PATH = (
        modified_policy
    )

    reload_response = client.post(
        "/policy/reload"
    )

    assert (
        reload_response.status_code
        == 200
    )

    assert (
        reload_response.json()[
            "policy_version"
        ]
        == "model-removed-test"
    )

    after = client.post(
        "/gateway/evaluate",
        json=_request(
            call_id=(
                "CALL-MODEL-AFTER-RELOAD"
            ),
            session_id=(
                "SESSION-MODEL-AFTER"
            ),
            model_name=(
                APPROVED_MODEL
            ),
        ),
    )

    assert after.status_code == 200

    payload = after.json()

    assert (
        payload["decision"]["action"]
        == "BLOCK"
    )

    assert (
        payload["executed"]
        is False
    )

    assert (
        "Unapproved model"
        in payload["decision"]["reason"]
    )