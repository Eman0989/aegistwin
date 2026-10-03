from app.controls.policy import PolicyEngine
from app.demo.scenario import run_legitimate_workflow, run_malicious_workflow
from app.security.compiler import compile_guardrail


async def run_attack_repair_replay() -> dict:
    policy = PolicyEngine()
    before = await run_malicious_workflow(policy)
    if before.attack_path is None:
        raise RuntimeError("Canonical attack was not reproduced")

    guardrail = compile_guardrail(before.attack_path)
    policy.install(guardrail)
    after = await run_malicious_workflow(policy)
    legitimate = await run_legitimate_workflow(policy)

    return {
        "before": before,
        "generated_guardrail": guardrail,
        "after": after,
        "legitimate_regression": legitimate,
        "summary": {
            "attack_before": "SUCCESSFUL" if not before.blocked else "BLOCKED",
            "attack_after": "BLOCKED" if after.blocked else "SUCCESSFUL",
            "legitimate_task": "ALLOWED" if legitimate.success else "BLOCKED",
        },
    }
