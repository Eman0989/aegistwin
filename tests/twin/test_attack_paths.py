from datetime import datetime, timezone

from app.contracts import (
    DataArtifact,
    InstructionOrigin,
    RiskLevel,
    ToolCall,
    ToolProfile,
)

from app.twin.attack_paths import (
    discover_attack_paths,
    find_critical_attack_paths,
)

from app.twin.graph import (
    build_twin_graph,
)


def make_profile(
    tool_name: str,
    *,
    capabilities: set[str],
    risk_level: RiskLevel,
) -> ToolProfile:
    return ToolProfile(
        tool_name=tool_name,
        version="1.0",
        declared_effects=set(),
        observed_effects=set(),
        capabilities=capabilities,
        risk_level=risk_level,
        behavioral_mismatch=False,
        fingerprint=(
            f"fingerprint-{tool_name}"
        ),
    )


def make_call(
    *,
    intent: str = "Summarize this invoice",
    origin: InstructionOrigin = (
        InstructionOrigin.WEB_UNTRUSTED
    ),
) -> ToolCall:
    return ToolCall(
        call_id="call-external-001",
        session_id="session-001",
        tool_name="external_http",
        arguments={},
        instruction_origin=origin,
        original_user_intent=intent,
        timestamp=datetime.now(
            timezone.utc
        ),
    )


def build_attack_demo_graph(
    *,
    intent: str = "Summarize this invoice",
    sensitive: bool = True,
):
    summarizer = make_profile(
        "summarizer",
        capabilities=set(),
        risk_level=RiskLevel.LOW,
    )

    external_http = make_profile(
        "external_http",
        capabilities={
            "external_communication",
        },
        risk_level=RiskLevel.HIGH,
    )

    customer = DataArtifact(
        artifact_id="customer",
        value={
            "name": "Demo Customer",
            "email": "demo@example.test",
        },
        labels=(
            {"CustomerPII"}
            if sensitive
            else {"PUBLIC"}
        ),
        parent_artifact_ids=set(),
        transformation=None,
    )

    summary = DataArtifact(
        artifact_id="summary",
        value="Invoice summary",
        labels=(
            {
                "DerivedFrom<CustomerPII>"
            }
            if sensitive
            else {"PUBLIC"}
        ),
        parent_artifact_ids={
            "customer",
        },
        transformation="summarizer",
    )

    outbound_payload = DataArtifact(
        artifact_id="outbound",
        value="Outbound payload",
        labels=(
            {
                "DerivedFrom<CustomerPII>"
            }
            if sensitive
            else {"PUBLIC"}
        ),
        parent_artifact_ids={
            "summary",
        },
        transformation="external_http",
    )

    return build_twin_graph(
        profiles=[
            summarizer,
            external_http,
        ],
        calls=[
            make_call(
                intent=intent
            )
        ],
        artifacts=[
            customer,
            summary,
            outbound_payload,
        ],
    )


def test_detects_sensitive_external_attack():
    graph = build_attack_demo_graph()

    attacks = discover_attack_paths(
        graph,
        final_effect=(
            "EXTERNAL_TRANSFER"
        ),
        destination="EXTERNAL",
        evidence_receipt_ids=[
            "receipt-001",
            "receipt-002",
        ],
    )

    assert len(attacks) == 1

    attack = attacks[0]

    assert (
        attack.risk_level
        == RiskLevel.CRITICAL
    )

    assert (
        attack.instruction_origin
        == InstructionOrigin.WEB_UNTRUSTED
    )

    assert (
        attack.original_intent
        == "Summarize this invoice"
    )

    assert (
        attack.final_effect
        == "EXTERNAL_TRANSFER"
    )

    assert (
        attack.destination
        == "EXTERNAL"
    )

    assert attack.reproducible is True


def test_attack_preserves_sensitive_lineage():
    graph = build_attack_demo_graph()

    attacks = discover_attack_paths(
        graph
    )

    attack = attacks[0]

    assert (
        "CustomerPII"
        in attack.source_labels
    )

    assert (
        "DerivedFrom<CustomerPII>"
        in attack.source_labels
    )


def test_attack_path_contains_external_tool():
    graph = build_attack_demo_graph()

    attacks = discover_attack_paths(
        graph
    )

    attack = attacks[0]

    assert (
        "tool:summarizer"
        in attack.path
    )

    assert (
        "tool:external_http"
        in attack.path
    )

    assert (
        "destination:EXTERNAL"
        in attack.path
    )


def test_public_data_does_not_create_attack():
    graph = build_attack_demo_graph(
        sensitive=False
    )

    attacks = discover_attack_paths(
        graph
    )

    assert attacks == []


def test_explicit_external_authorization_is_not_attack():
    graph = build_attack_demo_graph(
        intent=(
            "Send this report to "
            "finance@example.test"
        )
    )

    attacks = discover_attack_paths(
        graph
    )

    assert attacks == []


def test_attack_id_is_deterministic():
    graph = build_attack_demo_graph()

    first = discover_attack_paths(
        graph,
        evidence_receipt_ids=[
            "receipt-001",
        ],
    )

    second = discover_attack_paths(
        graph,
        evidence_receipt_ids=[
            "receipt-001",
        ],
    )

    assert (
        first[0].attack_id
        == second[0].attack_id
    )


def test_filter_critical_attacks():
    graph = build_attack_demo_graph()

    attacks = discover_attack_paths(
        graph
    )

    critical = (
        find_critical_attack_paths(
            attacks
        )
    )

    assert len(critical) == 1

    assert (
        critical[0].risk_level
        == RiskLevel.CRITICAL
    )