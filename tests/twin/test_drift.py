from app.contracts import (
    RiskLevel,
    ToolProfile,
)

from app.twin.drift import (
    analyze_behavioral_drift,
    build_drift_report,
)


def make_profile(
    *,
    tool_name: str = "invoice_reader",
    version: str = "1.0",
    effects: set[str] | None = None,
    capabilities: set[str] | None = None,
    risk_level: RiskLevel = (
        RiskLevel.LOW
    ),
    behavioral_mismatch: bool = False,
    fingerprint: str = "fingerprint-1",
) -> ToolProfile:
    return ToolProfile(
        tool_name=tool_name,
        version=version,
        declared_effects={
            "READ_INVOICE",
        },
        observed_effects=(
            effects
            if effects is not None
            else {"READ_INVOICE"}
        ),
        capabilities=(
            capabilities
            if capabilities is not None
            else set()
        ),
        risk_level=risk_level,
        behavioral_mismatch=(
            behavioral_mismatch
        ),
        fingerprint=fingerprint,
    )


def test_stable_tool_has_no_drift():
    previous = make_profile()

    current = make_profile()

    result = analyze_behavioral_drift(
        previous,
        current,
    )

    assert (
        result["drift_detected"]
        is False
    )

    assert (
        result["severity"]
        == "LOW"
    )

    assert (
        result["should_quarantine"]
        is False
    )


def test_detects_new_external_behavior():
    previous = make_profile(
        capabilities={
            "sensitive_data_access",
        },
        risk_level=RiskLevel.MEDIUM,
        fingerprint="old",
    )

    current = make_profile(
        effects={
            "READ_INVOICE",
            "SEND_HTTP_REQUEST",
        },
        capabilities={
            "sensitive_data_access",
            "external_communication",
        },
        risk_level=RiskLevel.CRITICAL,
        behavioral_mismatch=True,
        fingerprint="new",
    )

    result = analyze_behavioral_drift(
        previous,
        current,
    )

    assert (
        result["drift_detected"]
        is True
    )

    assert (
        "SEND_HTTP_REQUEST"
        in result["added_effects"]
    )

    assert (
        "external_communication"
        in result[
            "added_capabilities"
        ]
    )

    assert (
        result["severity"]
        == "CRITICAL"
    )

    assert (
        result["should_quarantine"]
        is True
    )

    assert (
        result["retest_required"]
        is True
    )


def test_detects_fingerprint_change():
    previous = make_profile(
        fingerprint="old"
    )

    current = make_profile(
        fingerprint="new"
    )

    result = analyze_behavioral_drift(
        previous,
        current,
    )

    assert (
        result["fingerprint_changed"]
        is True
    )

    assert (
        result["drift_detected"]
        is True
    )


def test_detects_version_change():
    previous = make_profile(
        version="1.0"
    )

    current = make_profile(
        version="1.1"
    )

    result = analyze_behavioral_drift(
        previous,
        current,
    )

    assert (
        result["version_changed"]
        is True
    )

    assert (
        result["retest_required"]
        is True
    )


def test_different_tools_cannot_be_compared():
    previous = make_profile(
        tool_name="invoice_reader"
    )

    current = make_profile(
        tool_name="external_http"
    )

    try:
        analyze_behavioral_drift(
            previous,
            current,
        )

        assert False

    except ValueError:
        assert True


def test_report_detects_new_tool():
    previous = [
        make_profile(
            tool_name="invoice_reader"
        )
    ]

    current = [
        make_profile(
            tool_name="invoice_reader"
        ),
        make_profile(
            tool_name="external_http",
            capabilities={
                "external_communication",
            },
            risk_level=RiskLevel.HIGH,
        ),
    ]

    report = build_drift_report(
        previous,
        current,
    )

    assert (
        report["summary"][
            "new_tools"
        ]
        == 1
    )

    assert (
        report["summary"][
            "quarantined_tools"
        ]
        == 1
    )

    assert (
        "external_http"
        in report["new_tools"]
    )


def test_report_detects_removed_tool():
    previous = [
        make_profile(
            tool_name="invoice_reader"
        ),
        make_profile(
            tool_name="old_tool"
        ),
    ]

    current = [
        make_profile(
            tool_name="invoice_reader"
        )
    ]

    report = build_drift_report(
        previous,
        current,
    )

    assert (
        report["summary"][
            "removed_tools"
        ]
        == 1
    )

    assert (
        report["removed_tools"]
        == ["old_tool"]
    )