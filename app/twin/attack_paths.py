from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from typing import Any

from app.contracts import (
    AttackPath,
    InstructionOrigin,
    RiskLevel,
    TwinGraph,
)

from app.twin.intent_action import (
    is_action_aligned,
)
from app.twin.lineage import (
    is_sensitive_label,
)
from app.twin.provenance import (
    most_restrictive_origin,
)


EXTERNAL_EFFECTS = {
    "EXTERNAL_TRANSFER",
    "SEND_EXTERNAL_DATA",
    "SEND_HTTP_REQUEST",
    "UPLOAD_EXTERNAL",
    "HTTP_POST",
    "EXTERNAL_NETWORK",
}


def _normalize(value: str) -> str:
    return value.strip().upper()


def _is_external_effect(
    effect: str,
) -> bool:
    return _normalize(effect) in EXTERNAL_EFFECTS


def _nodes_by_id(
    graph: TwinGraph,
) -> dict[str, dict[str, Any]]:
    return {
        node["id"]: node
        for node in graph.nodes
        if "id" in node
    }


def _infer_original_intent(
    graph: TwinGraph,
) -> str:
    """
    Recover the user intent stored inside the Digital Twin.
    """

    for node in graph.nodes:
        if (
            node.get("type")
            == "USER_INTENT"
        ):
            intent = node.get(
                "intent"
            )

            if intent:
                return str(intent)

    return ""


def _infer_instruction_origin(
    graph: TwinGraph,
) -> InstructionOrigin:
    """
    Recover all provenance sources from the graph and
    preserve the most restrictive one.
    """

    origins: list[
        InstructionOrigin
    ] = []

    for node in graph.nodes:
        if (
            node.get("type")
            != "INSTRUCTION_ORIGIN"
        ):
            continue

        value = node.get("origin")

        if not value:
            continue

        try:
            origins.append(
                InstructionOrigin(value)
            )
        except ValueError:
            continue

    if not origins:
        return InstructionOrigin.SYSTEM

    return most_restrictive_origin(
        origins
    )


def _incoming_derivation_parents(
    graph: TwinGraph,
    artifact_node_id: str,
) -> list[str]:
    """
    Return parent artifacts connected by DATA_DERIVATION.
    """

    parents = [
        edge["source"]
        for edge in graph.edges
        if (
            edge.get("target")
            == artifact_node_id
            and edge.get("relation")
            == "DATA_DERIVATION"
        )
    ]

    return sorted(parents)


def _artifact_ancestry(
    graph: TwinGraph,
    artifact_node_id: str,
) -> list[str]:
    """
    Reconstruct the artifact lineage from the original
    source to the final artifact.
    """

    visited: set[str] = set()
    ordered: list[str] = []

    def visit(
        node_id: str,
    ) -> None:
        if node_id in visited:
            return

        visited.add(node_id)

        parents = (
            _incoming_derivation_parents(
                graph,
                node_id,
            )
        )

        for parent_id in parents:
            visit(parent_id)

        ordered.append(node_id)

    visit(artifact_node_id)

    return ordered


def _collect_chain_labels(
    graph: TwinGraph,
    artifact_chain: Iterable[str],
) -> set[str]:
    """
    Collect all security labels observed across a lineage.
    """

    nodes = _nodes_by_id(
        graph
    )

    labels: set[str] = set()

    for node_id in artifact_chain:
        node = nodes.get(
            node_id,
            {}
        )

        labels.update(
            node.get(
                "labels",
                [],
            )
        )

    return labels


def _contains_sensitive_labels(
    labels: Iterable[str],
) -> bool:
    return any(
        is_sensitive_label(label)
        for label in labels
    )


def _build_readable_path(
    graph: TwinGraph,
    artifact_chain: list[str],
    destination: str | None,
) -> list[str]:
    """
    Convert artifact lineage into a readable attack chain.

    Example:

    artifact:customer
        ↓
    tool:summarizer
        ↓
    artifact:summary
        ↓
    tool:external_http
        ↓
    artifact:payload
        ↓
    destination:EXTERNAL
    """

    nodes = _nodes_by_id(
        graph
    )

    path: list[str] = []

    for index, artifact_id in enumerate(
        artifact_chain
    ):
        node = nodes.get(
            artifact_id,
            {}
        )

        transformation = node.get(
            "transformation"
        )

        if index > 0 and transformation:
            tool_id = (
                f"tool:{transformation}"
            )

            if (
                not path
                or path[-1] != tool_id
            ):
                path.append(
                    tool_id
                )

        path.append(
            artifact_id
        )

    if destination:
        path.append(
            f"destination:{destination}"
        )

    return path


def _generate_attack_id(
    *,
    original_intent: str,
    instruction_origin: InstructionOrigin,
    path: list[str],
    final_effect: str,
    destination: str | None,
) -> str:
    """
    Generate a deterministic attack ID so replaying the same
    attack produces the same identity.
    """

    payload = {
        "original_intent": (
            original_intent
        ),
        "instruction_origin": (
            instruction_origin.value
        ),
        "path": path,
        "final_effect": (
            _normalize(final_effect)
        ),
        "destination": destination,
    }

    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    digest = hashlib.sha256(
        encoded
    ).hexdigest()

    return (
        f"attack-{digest[:16]}"
    )


def discover_attack_paths(
    graph: TwinGraph,
    *,
    final_effect: str = "EXTERNAL_TRANSFER",
    destination: str | None = "EXTERNAL",
    evidence_receipt_ids: Iterable[str] = (),
    reproducible: bool = True,
) -> list[AttackPath]:
    """
    Search the Digital Twin for sensitive-data exfiltration paths.

    A path is considered a successful attack when:

    1. Sensitive or DerivedFrom<Sensitive> data exists.
    2. That data reaches a tool capable of external communication.
    3. The final effect crosses the trust boundary.
    4. The user's original intent did not explicitly authorize it.

    This implements the core AegisTwin attack definition.
    """

    normalized_effect = (
        _normalize(final_effect)
    )

    if not _is_external_effect(
        normalized_effect
    ):
        return []

    nodes = _nodes_by_id(
        graph
    )

    original_intent = (
        _infer_original_intent(
            graph
        )
    )

    instruction_origin = (
        _infer_instruction_origin(
            graph
        )
    )

    # Explicitly authorized external actions are not attacks.
    if is_action_aligned(
        original_intent,
        normalized_effect,
    ):
        return []

    receipt_ids = list(
        evidence_receipt_ids
    )

    attacks: list[
        AttackPath
    ] = []

    for node in graph.nodes:
        if (
            node.get("type")
            != "DATA_ARTIFACT"
        ):
            continue

        transformation = node.get(
            "transformation"
        )

        if not transformation:
            continue

        tool_id = (
            f"tool:{transformation}"
        )

        tool_node = nodes.get(
            tool_id
        )

        if not tool_node:
            continue

        capabilities = set(
            tool_node.get(
                "capabilities",
                [],
            )
        )

        # Final sink must be capable of communicating externally.
        if (
            "external_communication"
            not in capabilities
        ):
            continue

        artifact_node_id = node[
            "id"
        ]

        artifact_chain = (
            _artifact_ancestry(
                graph,
                artifact_node_id,
            )
        )

        source_labels = (
            _collect_chain_labels(
                graph,
                artifact_chain,
            )
        )

        if not _contains_sensitive_labels(
            source_labels
        ):
            continue

        attack_path = (
            _build_readable_path(
                graph,
                artifact_chain,
                destination,
            )
        )

        attack_id = (
            _generate_attack_id(
                original_intent=(
                    original_intent
                ),
                instruction_origin=(
                    instruction_origin
                ),
                path=attack_path,
                final_effect=(
                    normalized_effect
                ),
                destination=destination,
            )
        )

        attacks.append(
            AttackPath(
                attack_id=attack_id,
                original_intent=(
                    original_intent
                ),
                instruction_origin=(
                    instruction_origin
                ),
                path=attack_path,
                final_effect=(
                    normalized_effect
                ),
                source_labels=(
                    source_labels
                ),
                destination=destination,
                risk_level=(
                    RiskLevel.CRITICAL
                ),
                reproducible=(
                    reproducible
                ),
                evidence_receipt_ids=(
                    receipt_ids
                ),
            )
        )

    return attacks


def find_critical_attack_paths(
    attacks: Iterable[AttackPath],
) -> list[AttackPath]:
    """
    Convenience filter for reporting and guardrail synthesis.
    """

    return [
        attack
        for attack in attacks
        if (
            attack.risk_level
            == RiskLevel.CRITICAL
        )
    ]