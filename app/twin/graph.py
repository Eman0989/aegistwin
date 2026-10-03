from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from app.contracts import (
    DataArtifact,
    ToolCall,
    ToolProfile,
    TwinGraph,
)


def _add_node(
    nodes: dict[str, dict[str, Any]],
    node: dict[str, Any],
) -> None:
    """
    Add a node only once.

    Node IDs are globally unique inside the Twin Graph.
    """
    nodes[node["id"]] = node


def _add_edge(
    edges: list[dict[str, Any]],
    *,
    source: str,
    target: str,
    relation: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    """
    Add a directed relationship between two Twin Graph nodes.
    """
    edge = {
        "source": source,
        "target": target,
        "relation": relation,
    }

    if metadata:
        edge["metadata"] = metadata

    edges.append(edge)


def tool_profile_to_node(
    profile: ToolProfile,
) -> dict[str, Any]:
    """
    Convert ToolProfile into a Digital Twin tool node.
    """
    return {
        "id": f"tool:{profile.tool_name}",
        "type": "TOOL",
        "name": profile.tool_name,
        "version": profile.version,
        "declared_effects": sorted(
            profile.declared_effects
        ),
        "observed_effects": sorted(
            profile.observed_effects
        ),
        "capabilities": sorted(
            profile.capabilities
        ),
        "risk_level": (
            profile.risk_level.value
        ),
        "behavioral_mismatch": (
            profile.behavioral_mismatch
        ),
        "fingerprint": profile.fingerprint,
    }


def tool_call_to_node(
    call: ToolCall,
) -> dict[str, Any]:
    """
    Convert one observed runtime tool call into a graph node.
    """
    return {
        "id": f"call:{call.call_id}",
        "type": "TOOL_CALL",
        "call_id": call.call_id,
        "session_id": call.session_id,
        "tool_name": call.tool_name,
        "arguments": call.arguments,
        "instruction_origin": (
            call.instruction_origin.value
        ),
        "original_user_intent": (
            call.original_user_intent
        ),
        "timestamp": (
            call.timestamp.isoformat()
            if call.timestamp
            else None
        ),
    }


def artifact_to_node(
    artifact: DataArtifact,
) -> dict[str, Any]:
    """
    Convert a DataArtifact into a lineage-aware graph node.
    """
    return {
        "id": (
            f"artifact:{artifact.artifact_id}"
        ),
        "type": "DATA_ARTIFACT",
        "artifact_id": (
            artifact.artifact_id
        ),
        "labels": sorted(
            artifact.labels
        ),
        "parent_artifact_ids": sorted(
            artifact.parent_artifact_ids
        ),
        "transformation": (
            artifact.transformation
        ),
    }


def build_twin_graph(
    *,
    profiles: Iterable[ToolProfile] = (),
    calls: Iterable[ToolCall] = (),
    artifacts: Iterable[DataArtifact] = (),
) -> TwinGraph:
    """
    Build AegisTwin's executable Digital Twin graph.

    Graph contains:

    USER INTENT
        ↓
    INSTRUCTION PROVENANCE
        ↓
    TOOL CALL
        ↓
    TOOL
        ↓
    DATA ARTIFACT / LINEAGE

    This structure is intentionally generic so that
    Attack Path Discovery can search it later.
    """

    profiles = list(profiles)
    calls = list(calls)
    artifacts = list(artifacts)

    nodes: dict[
        str,
        dict[str, Any],
    ] = {}

    edges: list[
        dict[str, Any]
    ] = []

    profile_names = {
        profile.tool_name
        for profile in profiles
    }

    # --------------------------------------------------
    # TOOL NODES
    # --------------------------------------------------

    for profile in profiles:
        node = tool_profile_to_node(
            profile
        )

        _add_node(
            nodes,
            node,
        )

    # --------------------------------------------------
    # TOOL CALL + PROVENANCE + INTENT
    # --------------------------------------------------

    for call in calls:
        call_node = tool_call_to_node(
            call
        )

        _add_node(
            nodes,
            call_node,
        )

        tool_id = (
            f"tool:{call.tool_name}"
        )

        # If runtime calls a tool that does not yet
        # have a Tool MRI profile, preserve it anyway.
        if call.tool_name not in profile_names:
            _add_node(
                nodes,
                {
                    "id": tool_id,
                    "type": "TOOL",
                    "name": call.tool_name,
                    "profile_status": (
                        "UNPROFILED"
                    ),
                },
            )

        _add_edge(
            edges,
            source=(
                f"call:{call.call_id}"
            ),
            target=tool_id,
            relation="INVOKES",
        )

        # Instruction provenance node
        origin_value = (
            call.instruction_origin.value
        )

        origin_id = (
            f"origin:{origin_value}"
        )

        _add_node(
            nodes,
            {
                "id": origin_id,
                "type": (
                    "INSTRUCTION_ORIGIN"
                ),
                "origin": origin_value,
            },
        )

        _add_edge(
            edges,
            source=origin_id,
            target=(
                f"call:{call.call_id}"
            ),
            relation=(
                "INSTRUCTION_PROVENANCE"
            ),
        )

        # Original user intent node
        intent_id = (
            f"intent:{call.session_id}"
        )

        _add_node(
            nodes,
            {
                "id": intent_id,
                "type": "USER_INTENT",
                "session_id": (
                    call.session_id
                ),
                "intent": (
                    call.original_user_intent
                ),
            },
        )

        _add_edge(
            edges,
            source=intent_id,
            target=(
                f"call:{call.call_id}"
            ),
            relation="INTENT_CONTEXT",
        )

    # --------------------------------------------------
    # DATA ARTIFACTS + LINEAGE
    # --------------------------------------------------

    artifact_ids = {
        artifact.artifact_id
        for artifact in artifacts
    }

    for artifact in artifacts:
        node = artifact_to_node(
            artifact
        )

        _add_node(
            nodes,
            node,
        )

    for artifact in artifacts:
        current_id = (
            f"artifact:{artifact.artifact_id}"
        )

        # Parent → child lineage edges
        for parent_id in (
            artifact.parent_artifact_ids
        ):
            parent_node_id = (
                f"artifact:{parent_id}"
            )

            # Preserve missing lineage evidence
            # as an unresolved artifact node.
            if parent_id not in artifact_ids:
                _add_node(
                    nodes,
                    {
                        "id": parent_node_id,
                        "type": (
                            "DATA_ARTIFACT"
                        ),
                        "artifact_id": (
                            parent_id
                        ),
                        "status": (
                            "UNRESOLVED"
                        ),
                    },
                )

            _add_edge(
                edges,
                source=parent_node_id,
                target=current_id,
                relation="DATA_DERIVATION",
            )

        # If transformation matches a known tool,
        # link the tool to the produced artifact.
        if (
            artifact.transformation
            and artifact.transformation
            in profile_names
        ):
            _add_edge(
                edges,
                source=(
                    "tool:"
                    f"{artifact.transformation}"
                ),
                target=current_id,
                relation="PRODUCES",
            )

    return TwinGraph(
        nodes=list(nodes.values()),
        edges=edges,
    )


def find_nodes_by_type(
    graph: TwinGraph,
    node_type: str,
) -> list[dict[str, Any]]:
    """
    Utility used later by attack path discovery.
    """
    return [
        node
        for node in graph.nodes
        if node.get("type")
        == node_type
    ]


def find_outgoing_edges(
    graph: TwinGraph,
    node_id: str,
) -> list[dict[str, Any]]:
    """
    Return all outgoing relationships from one node.
    """
    return [
        edge
        for edge in graph.edges
        if edge.get("source")
        == node_id
    ]


def find_incoming_edges(
    graph: TwinGraph,
    node_id: str,
) -> list[dict[str, Any]]:
    """
    Return all incoming relationships to one node.
    """
    return [
        edge
        for edge in graph.edges
        if edge.get("target")
        == node_id
    ]