from app.contracts import DataArtifact, DecisionAction, EffectReceipt, PolicyDecision, ToolCall
from app.controls.policy import PolicyEngine
from app.gateway.executor import execute_tool


class Gateway:
    def __init__(self, policy_engine: PolicyEngine) -> None:
        self.policy_engine = policy_engine

    async def process(
        self,
        call: ToolCall,
        input_artifacts: list[DataArtifact] | None = None,
    ) -> tuple[PolicyDecision, EffectReceipt | None]:
        inputs = list(input_artifacts or [])
        labels = set().union(*(a.labels for a in inputs)) if inputs else set()
        destination = "EXTERNAL" if call.tool_name == "external_http" else None
        decision = self.policy_engine.evaluate(call, labels, destination)
        if decision.action == DecisionAction.BLOCK:
            return decision, None
        return decision, await execute_tool(call, inputs)
