from datetime import datetime, timezone

from app.contracts import (
    DataArtifact,
    InstructionOrigin,
    RiskLevel,
    ToolCall,
    ToolProfile,
    TwinGraph,
)

from app.twin.graph import (
    build_twin_graph,
    find_incoming_edges,
    find_nodes_by_type,
    find_outgoing_edges,
)


def make_profile(
    tool_name: str,
) -> ToolProfile:
    return ToolProfile(
        tool_name=tool_name,
        version="1.0",
        declared_effects={
            "READ_DATA",
        },
        observed_effects={
            "READ_DATA",
        },
        capabilities={
            "database_access",
        },
        risk_level=RiskLevel.MEDIUM,
        behavioral_mismatch=False,
        fingerprint="test123",
    )


def make_call() -> ToolCall:
    return ToolCall(
        call_id="call-001",
        session_id="session-001",
        tool_name="customer_database",
        arguments={
            "customer_id": "CUST-001",
        },
        instruction_origin=(
            InstructionOrigin.WEB_UNTRUSTED
        ),
        original_user_intent=(
            "Summarize this invoice"
        ),
        timestamp=datetime.now(
            timezone.utc
        ),
    )


def test_build_twin_graph_returns_contract():
    graph = build_twin_graph(
        profiles=[
            make_profile(
                "customer_database"
            )
        ],
        calls=[
            make_call()
        ],
    )

    assert isinstance(
        graph,
        TwinGraph,
    )

    assert len(
        graph.nodes
    ) > 0

    assert len(
        graph.edges
    ) > 0


def test_graph_connects_call_to_tool():
    graph = build_twin_graph(
        profiles=[
            make_profile(
                "customer_database"
            )
        ],
        calls=[
            make_call()
        ],
    )

    edges = find_outgoing_edges(
        graph,
        "call:call-001",
    )

    assert any(
        edge["target"]
        == "tool:customer_database"
        and edge["relation"]
        == "INVOKES"
        for edge in edges
    )


def test_graph_preserves_untrusted_provenance():
    graph = build_twin_graph(
        profiles=[
            make_profile(
                "customer_database"
            )
        ],
        calls=[
            make_call()
        ],
    )

    incoming = find_incoming_edges(
        graph,
        "call:call-001",
    )

    assert any(
        edge["source"]
        == "origin:WEB_UNTRUSTED"
        and edge["relation"]
        == "INSTRUCTION_PROVENANCE"
        for edge in incoming
    )


def test_graph_contains_user_intent():
    graph = build_twin_graph(
        profiles=[
            make_profile(
                "customer_database"
            )
        ],
        calls=[
            make_call()
        ],
    )

    intent_nodes = find_nodes_by_type(
        graph,
        "USER_INTENT",
    )

    assert len(
        intent_nodes
    ) == 1

    assert (
        intent_nodes[0]["intent"]
        == "Summarize this invoice"
    )


def test_graph_preserves_data_lineage():
    customer = DataArtifact(
        artifact_id="customer",
        value={
            "email": "demo@example.test"
        },
        labels={
            "CustomerPII",
        },
        parent_artifact_ids=set(),
        transformation=None,
    )

    summary = DataArtifact(
        artifact_id="summary",
        value="invoice summary",
        labels={
            "DerivedFrom<CustomerPII>",
        },
        parent_artifact_ids={
            "customer",
        },
        transformation="summarizer",
    )

    graph = build_twin_graph(
        profiles=[
            make_profile(
                "summarizer"
            )
        ],
        artifacts=[
            customer,
            summary,
        ],
    )

    incoming = find_incoming_edges(
        graph,
        "artifact:summary",
    )

    assert any(
        edge["source"]
        == "artifact:customer"
        and edge["relation"]
        == "DATA_DERIVATION"
        for edge in incoming
    )

    assert any(
        edge["source"]
        == "tool:summarizer"
        and edge["relation"]
        == "PRODUCES"
        for edge in incoming
    )


def test_unprofiled_tool_is_preserved():
    call = ToolCall(
        call_id="call-999",
        session_id="session-001",
        tool_name="unknown_tool",
        arguments={},
        instruction_origin=(
            InstructionOrigin.USER
        ),
        original_user_intent="Test",
        timestamp=datetime.now(
            timezone.utc
        ),
    )

    graph = build_twin_graph(
        calls=[call]
    )

    tool_nodes = [
        node
        for node in graph.nodes
        if node["id"]
        == "tool:unknown_tool"
    ]

    assert len(
        tool_nodes
    ) == 1

    assert (
        tool_nodes[0]["profile_status"]
        == "UNPROFILED"
    )