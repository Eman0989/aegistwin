from app.contracts import RiskLevel, ToolProfile

from app.twin.capability_map import (
    build_capability_map,
    build_tool_capability_entry,
)


def test_build_single_tool_capability_entry():
    profile = ToolProfile(
        tool_name="customer_database",
        version="1.0",
        declared_effects={
            "READ_CUSTOMER_RECORD",
        },
        observed_effects={
            "READ_CUSTOMER_RECORD",
            "READ_CUSTOMER_PII",
        },
        capabilities={
            "database_access",
            "sensitive_data_access",
        },
        risk_level=RiskLevel.MEDIUM,
        behavioral_mismatch=True,
        fingerprint="abc123",
    )

    result = build_tool_capability_entry(
        profile
    )

    assert (
        result["tool_name"]
        == "customer_database"
    )

    assert (
        result["risk_level"]
        == "MEDIUM"
    )

    assert (
        result["behavioral_mismatch"]
        is True
    )

    assert (
        result["capability_flags"][
            "database_access"
        ]
        is True
    )

    assert (
        result["capability_flags"][
            "sensitive_data_access"
        ]
        is True
    )

    assert (
        result["capability_flags"][
            "external_communication"
        ]
        is False
    )


def test_build_complete_capability_map():
    database = ToolProfile(
        tool_name="customer_database",
        version="1.0",
        declared_effects={
            "READ_CUSTOMER_RECORD",
        },
        observed_effects={
            "READ_CUSTOMER_PII",
        },
        capabilities={
            "database_access",
            "sensitive_data_access",
        },
        risk_level=RiskLevel.MEDIUM,
        behavioral_mismatch=True,
        fingerprint="db123",
    )

    external_http = ToolProfile(
        tool_name="external_http",
        version="1.0",
        declared_effects={
            "SEND_HTTP_REQUEST",
        },
        observed_effects={
            "SEND_HTTP_REQUEST",
            "EXTERNAL_NETWORK",
        },
        capabilities={
            "external_communication",
        },
        risk_level=RiskLevel.HIGH,
        behavioral_mismatch=True,
        fingerprint="http123",
    )

    dangerous_tool = ToolProfile(
        tool_name="dangerous_tool",
        version="1.0",
        declared_effects={
            "READ_DATA",
        },
        observed_effects={
            "READ_DATA",
            "SEND_HTTP_REQUEST",
        },
        capabilities={
            "sensitive_data_access",
            "external_communication",
        },
        risk_level=RiskLevel.CRITICAL,
        behavioral_mismatch=True,
        fingerprint="danger123",
    )

    result = build_capability_map(
        [
            database,
            external_http,
            dangerous_tool,
        ]
    )

    assert (
        result["summary"]["total_tools"]
        == 3
    )

    assert (
        result["summary"]["critical_tools"]
        == 1
    )

    assert (
        result["summary"]["high_risk_tools"]
        == 1
    )

    assert (
        result["summary"][
            "behavioral_mismatches"
        ]
        == 3
    )

    assert (
        result["summary"][
            "external_communication_tools"
        ]
        == 2
    )

    assert (
        result["summary"][
            "sensitive_data_tools"
        ]
        == 2
    )

    assert (
        result["tools"][0]["tool_name"]
        == "customer_database"
    )