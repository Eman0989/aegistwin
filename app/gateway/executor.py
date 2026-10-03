from hashlib import sha256
import json
from uuid import uuid4

from app.contracts import DataArtifact, EffectReceipt, ToolCall
from app.demo.mock_tools import DECLARED_EFFECTS, TOOL_FUNCTIONS


def _fingerprint(tool_name: str, effect_names: list[str], version: str) -> str:
    payload = json.dumps(
        {"tool": tool_name, "effects": sorted(effect_names), "version": version},
        sort_keys=True,
    ).encode()
    return sha256(payload).hexdigest()


async def execute_tool(
    call: ToolCall,
    input_artifacts: list[DataArtifact] | None = None,
) -> EffectReceipt:
    if call.tool_name not in TOOL_FUNCTIONS:
        return EffectReceipt(
            receipt_id=f"RCP-{uuid4().hex[:8]}",
            call=call,
            declared_effects=[],
            succeeded=False,
            error=f"Unknown tool: {call.tool_name}",
        )

    inputs = list(input_artifacts or [])
    tool = TOOL_FUNCTIONS[call.tool_name]
    if call.tool_name in {"summarizer", "external_http"}:
        artifacts, effects = tool(call, inputs)
    else:
        artifacts, effects = tool(call)
    names = [e.effect_type for e in effects]
    return EffectReceipt(
        receipt_id=f"RCP-{uuid4().hex[:8]}",
        call=call,
        declared_effects=DECLARED_EFFECTS[call.tool_name],
        observed_effects=effects,
        input_artifact_ids=[a.artifact_id for a in inputs],
        output_artifacts=artifacts,
        tool_version="1.0.0",
        tool_fingerprint=_fingerprint(call.tool_name, names, "1.0.0"),
        succeeded=True,
    )
