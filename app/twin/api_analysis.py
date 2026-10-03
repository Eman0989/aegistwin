from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from typing import Any

from app.contracts import (
    DataArtifact,
    EffectReceipt,
    RiskLevel,
    ToolProfile,
)

from app.twin.attack_paths import discover_attack_paths
from app.twin.capability_map import build_capability_map
from app.twin.graph import build_twin_graph
from app.twin.intent_action import analyze_intent_action
from app.twin.least_privilege import build_least_privilege_plan
from app.twin.lineage import (
    contains_sensitive_lineage,
    is_sensitive_label,
    trace_lineage,
)
from app.twin.provenance import (
    analyze_tool_call_provenance,
    build_provenance_chain,
)
from app.twin.tool_mri import analyze_tool


def _group_receipts_by_tool(
    receipts: Iterable[EffectReceipt],
) -> dict[str, list[EffectReceipt]]:
    grouped: dict[str, list[EffectReceipt]] = defaultdict(list)

    for receipt in receipts:
        grouped[receipt.call.tool_name].append(receipt)

    return dict(grouped)


def _build_declared_profile(
    tool_name: str,
    receipts: list[EffectReceipt],
) -> ToolProfile:
    """
    Build the declared ToolProfile directly from runtime receipts.

    We intentionally use the receipt's declared_effects and tool version
    instead of creating a second source of truth.
    """

    declared_effects: set[str] = set()

    for receipt in receipts:
        declared_effects.update(receipt.declared_effects)

    latest_receipt = receipts[-1]

    return ToolProfile(
        tool_name=tool_name,
        version=latest_receipt.tool_version,
        declared_effects=declared_effects,
        observed_effects=set(),
        capabilities=set(),
        risk_level=RiskLevel.LOW,
        behavioral_mismatch=False,
        fingerprint=latest_receipt.tool_fingerprint,
    )


def _build_tool_profiles(
    receipts: list[EffectReceipt],
) -> list[ToolProfile]:
    """
    Run Tool MRI against each tool observed in the canonical workflow.
    """

    grouped = _group_receipts_by_tool(receipts)

    profiles: list[ToolProfile] = []

    for tool_name, tool_receipts in grouped.items():
        declared_profile = _build_declared_profile(
            tool_name,
            tool_receipts,
        )

        analyzed_profile = analyze_tool(
            declared_profile,
            tool_receipts,
        )

        profiles.append(analyzed_profile)

    profiles.sort(
        key=lambda profile: profile.tool_name
    )

    return profiles


def _collect_raw_artifacts(
    receipts: Iterable[EffectReceipt],
) -> list[DataArtifact]:
    """
    Collect the original artifacts exactly as produced by runtime.
    """

    artifacts: list[DataArtifact] = []

    for receipt in receipts:
        artifacts.extend(receipt.output_artifacts)

    return artifacts


def _collect_graph_artifacts(
    receipts: Iterable[EffectReceipt],
) -> list[DataArtifact]:
    """
    Produce graph-ready artifacts.

    Runtime artifacts use transformations such as 'summarize' or
    'external_send'. The Twin graph associates produced artifacts with
    tool names, so we preserve all artifact data but use the actual
    runtime tool name as the transformation identifier for the graph.
    """

    artifacts: list[DataArtifact] = []

    for receipt in receipts:
        for artifact in receipt.output_artifacts:
            artifacts.append(
                DataArtifact(
                    artifact_id=artifact.artifact_id,
                    value=artifact.value,
                    labels=set(artifact.labels),
                    parent_artifact_ids=set(
                        artifact.parent_artifact_ids
                    ),
                    transformation=receipt.call.tool_name,
                )
            )

    return artifacts


def _destination_for_receipt(
    receipt: EffectReceipt,
) -> str | None:
    """
    Recover the trust-boundary destination from observed effects.
    """

    for effect in receipt.observed_effects:
        if effect.destination:
            return str(effect.destination)

        destination_class = effect.metadata.get(
            "destination_class"
        )

        if destination_class:
            return str(destination_class)

    return None


def _semantic_effect_for_receipt(
    receipt: EffectReceipt,
) -> str:
    """
    Convert low-level runtime effects into the semantic action used by
    intent/action and attack-path analysis.
    """

    destination = _destination_for_receipt(receipt)

    if (
        destination is not None
        and destination.upper() == "EXTERNAL"
    ):
        return "EXTERNAL_TRANSFER"

    if receipt.observed_effects:
        return receipt.observed_effects[0].effect_type

    return "UNKNOWN"


def _build_provenance_report(
    receipts: list[EffectReceipt],
) -> dict[str, Any]:
    calls = [
        receipt.call
        for receipt in receipts
    ]

    per_call = []

    for receipt in receipts:
        per_call.append(
            analyze_tool_call_provenance(
                receipt.call,
                requested_effect=(
                    _semantic_effect_for_receipt(
                        receipt
                    )
                ),
            )
        )

    return {
        "chain": build_provenance_chain(
            calls
        ),
        "calls": per_call,
    }


def _build_intent_action_report(
    receipts: list[EffectReceipt],
) -> list[dict[str, Any]]:
    analyses: list[dict[str, Any]] = []

    for receipt in receipts:
        analyses.append(
            analyze_intent_action(
                original_intent=(
                    receipt.call.original_user_intent
                ),
                final_effect=(
                    _semantic_effect_for_receipt(
                        receipt
                    )
                ),
                destination=(
                    _destination_for_receipt(
                        receipt
                    )
                ),
            )
        )

    return analyses


def _build_lineage_report(
    artifacts: list[DataArtifact],
) -> dict[str, Any]:
    """
    Produce frontend-friendly sensitive-data lineage information.
    """

    sensitive_labels: set[str] = set()
    sensitive_artifact_ids: list[str] = []
    traces: dict[str, list[str]] = {}

    for artifact in artifacts:
        for label in artifact.labels:
            if is_sensitive_label(label):
                sensitive_labels.add(label)

        if contains_sensitive_lineage(
            artifact
        ):
            sensitive_artifact_ids.append(
                artifact.artifact_id
            )

            traces[
                artifact.artifact_id
            ] = trace_lineage(
                artifact.artifact_id,
                artifacts,
            )

    return {
        "sensitive_labels": sorted(
            sensitive_labels
        ),
        "sensitive_artifact_ids": (
            sensitive_artifact_ids
        ),
        "traces": traces,
        "artifacts": artifacts,
    }


def _build_legitimate_effect_map(
    legitimate_receipts: Iterable[
        EffectReceipt
    ],
) -> dict[str, set[str]]:
    """
    Determine which capabilities are actually needed by the legitimate
    regression workflow.
    """

    effects_by_tool: dict[
        str,
        set[str],
    ] = defaultdict(set)

    for receipt in legitimate_receipts:
        for effect in receipt.observed_effects:
            effects_by_tool[
                receipt.call.tool_name
            ].add(
                effect.effect_type
            )

    return dict(effects_by_tool)


def build_twin_analysis(
    *,
    receipts: Iterable[EffectReceipt],
    legitimate_receipts: Iterable[
        EffectReceipt
    ] = (),
) -> dict[str, Any]:
    """
    Build the complete Twin Intelligence response consumed by the
    frontend.

    Every value is generated from runtime evidence and existing Twin
    modules. No frontend/demo security result is hardcoded here.
    """

    receipts = list(receipts)
    legitimate_receipts = list(
        legitimate_receipts
    )

    if not receipts:
        return {
            "tool_profiles": [],
            "capability_map": {
                "summary": {
                    "total_tools": 0,
                },
                "tools": [],
            },
            "graph": {
                "nodes": [],
                "edges": [],
            },
            "provenance": {
                "chain": {},
                "calls": [],
            },
            "intent_action": [],
            "lineage": {
                "sensitive_labels": [],
                "sensitive_artifact_ids": [],
                "traces": {},
                "artifacts": [],
            },
            "attack_paths": [],
            "least_privilege": {
                "summary": {
                    "total_tools": 0,
                    "tools_with_excess_privilege": 0,
                    "total_removable_capabilities": 0,
                },
                "recommendations": [],
            },
            "drift": {
                "available": False,
                "reason": (
                    "No runtime evidence is available "
                    "for drift comparison."
                ),
                "report": None,
            },
        }

    # --------------------------------------------------
    # TOOL MRI
    # --------------------------------------------------

    tool_profiles = (
        _build_tool_profiles(
            receipts
        )
    )

    # --------------------------------------------------
    # CAPABILITY MAP
    # --------------------------------------------------

    capability_map = (
        build_capability_map(
            tool_profiles
        )
    )

    # --------------------------------------------------
    # RUNTIME CALLS + ARTIFACTS
    # --------------------------------------------------

    calls = [
        receipt.call
        for receipt in receipts
    ]

    raw_artifacts = (
        _collect_raw_artifacts(
            receipts
        )
    )

    graph_artifacts = (
        _collect_graph_artifacts(
            receipts
        )
    )

    # --------------------------------------------------
    # DIGITAL TWIN GRAPH
    # --------------------------------------------------

    graph = build_twin_graph(
        profiles=tool_profiles,
        calls=calls,
        artifacts=graph_artifacts,
    )

    # --------------------------------------------------
    # PROVENANCE
    # --------------------------------------------------

    provenance = (
        _build_provenance_report(
            receipts
        )
    )

    # --------------------------------------------------
    # INTENT VS ACTION
    # --------------------------------------------------

    intent_action = (
        _build_intent_action_report(
            receipts
        )
    )

    # --------------------------------------------------
    # DATA LINEAGE
    # --------------------------------------------------

    lineage = _build_lineage_report(
        raw_artifacts
    )

    # --------------------------------------------------
    # ATTACK PATH DISCOVERY
    # --------------------------------------------------

    external_destination: (
        str | None
    ) = None

    for receipt in receipts:
        destination = (
            _destination_for_receipt(
                receipt
            )
        )

        if (
            destination is not None
            and destination.upper()
            == "EXTERNAL"
        ):
            external_destination = (
                destination
            )
            break

    if external_destination:
        attack_paths = (
            discover_attack_paths(
                graph,
                final_effect=(
                    "EXTERNAL_TRANSFER"
                ),
                destination=(
                    external_destination
                ),
                evidence_receipt_ids=[
                    receipt.receipt_id
                    for receipt in receipts
                ],
                reproducible=True,
            )
        )
    else:
        attack_paths = []

    # --------------------------------------------------
    # LEAST PRIVILEGE
    # --------------------------------------------------

    legitimate_effects = (
        _build_legitimate_effect_map(
            legitimate_receipts
        )
    )

    least_privilege = (
        build_least_privilege_plan(
            tool_profiles,
            legitimate_effects,
        )
    )

    # --------------------------------------------------
    # DRIFT
    # --------------------------------------------------
    #
    # Drift requires a real previous behavioral snapshot.
    # The canonical attack demo contains one current snapshot,
    # so we explicitly report that drift comparison is unavailable
    # rather than fabricating a security finding.
    # --------------------------------------------------

    drift = {
        "available": False,
        "reason": (
            "A previous behavioral profile snapshot "
            "is required for temporal drift analysis."
        ),
        "report": None,
    }

    return {
        "tool_profiles": (
            tool_profiles
        ),
        "capability_map": (
            capability_map
        ),
        "graph": graph,
        "provenance": provenance,
        "intent_action": (
            intent_action
        ),
        "lineage": lineage,
        "attack_paths": (
            attack_paths
        ),
        "least_privilege": (
            least_privilege
        ),
        "drift": drift,
    }