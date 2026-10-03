from app.contracts import (
    RiskLevel,
    ToolProfile,
)

from app.twin.least_privilege import (
    analyze_least_privilege,
    build_least_privilege_plan,
    find_excess_capabilities,
    find_missing_capabilities,
    infer_required_capabilities,
)


def make_profile(
    *,
    tool_name: str = "customer_database",
    capabilities: set[str],
) -> ToolProfile:
    return ToolProfile(
        tool_name=tool_name,
        version="1.0",
        declared_effects=set(),
        observed_effects=set(),
        capabilities=capabilities,
        risk_level=RiskLevel.MEDIUM,
        behavioral_mismatch=False,
        fingerprint=(
            f"fingerprint-{tool_name}"
        ),
    )


def test_infer_database_and_sensitive_requirements():
    result = infer_required_capabilities(
        {
            "READ_CUSTOMER_PII",
        }
    )

    assert result == {
        "database_access",
        "sensitive_data_access",
    }


def test_detects_excess_external_permission():
    profile = make_profile(
        capabilities={
            "database_access",
            "sensitive_data_access",
            "external_communication",
        }
    )

    excess = find_excess_capabilities(
        profile,
        {
            "database_access",
            "sensitive_data_access",
        },
    )

    assert excess == {
        "external_communication",
    }


def test_detects_missing_required_permission():
    profile = make_profile(
        capabilities={
            "database_access",
        }
    )

    missing = find_missing_capabilities(
        profile,
        {
            "database_access",
            "sensitive_data_access",
        },
    )

    assert missing == {
        "sensitive_data_access",
    }


def test_aegistwin_removes_unnecessary_external_access():
    profile = make_profile(
        capabilities={
            "database_access",
            "sensitive_data_access",
            "external_communication",
        }
    )

    result = analyze_least_privilege(
        profile,
        legitimate_effects={
            "READ_CUSTOMER_PII",
        },
    )

    assert (
        result[
            "required_capabilities"
        ]
        == [
            "database_access",
            "sensitive_data_access",
        ]
    )

    assert (
        result[
            "removable_capabilities"
        ]
        == [
            "external_communication",
        ]
    )

    assert (
        result[
            "least_privilege_satisfied"
        ]
        is False
    )

    assert (
        result["reduction_percent"]
        == 33.33
    )


def test_exact_permissions_satisfy_least_privilege():
    profile = make_profile(
        capabilities={
            "database_access",
            "sensitive_data_access",
        }
    )

    result = analyze_least_privilege(
        profile,
        legitimate_effects={
            "READ_CUSTOMER_PII",
        },
    )

    assert (
        result[
            "removable_capabilities"
        ]
        == []
    )

    assert (
        result[
            "missing_capabilities"
        ]
        == []
    )

    assert (
        result[
            "least_privilege_satisfied"
        ]
        is True
    )


def test_build_complete_least_privilege_plan():
    database = make_profile(
        tool_name="customer_database",
        capabilities={
            "database_access",
            "sensitive_data_access",
            "external_communication",
        },
    )

    external_http = make_profile(
        tool_name="external_http",
        capabilities={
            "external_communication",
        },
    )

    result = build_least_privilege_plan(
        [
            database,
            external_http,
        ],
        {
            "customer_database": {
                "READ_CUSTOMER_PII",
            },
            "external_http": {
                "SEND_HTTP_REQUEST",
            },
        },
    )

    assert (
        result["summary"][
            "total_tools"
        ]
        == 2
    )

    assert (
        result["summary"][
            "tools_with_excess_privilege"
        ]
        == 1
    )

    assert (
        result["summary"][
            "total_removable_capabilities"
        ]
        == 1
    )