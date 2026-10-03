import pytest

from app.security.replay import run_attack_repair_replay


@pytest.mark.asyncio
async def test_attack_repair_replay_preserves_legitimate_workflow():
    result = await run_attack_repair_replay()

    assert result["before"].blocked is False
    assert result["before"].attack_path is not None
    assert result["before"].attack_path.risk_level.value == "CRITICAL"
    assert result["after"].blocked is True
    assert result["legitimate_regression"].success is True
    assert result["summary"] == {
        "attack_before": "SUCCESSFUL",
        "attack_after": "BLOCKED",
        "legitimate_task": "ALLOWED",
    }
