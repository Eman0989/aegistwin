from app.contracts import DataArtifact

from app.twin.lineage import (
    contains_sensitive_lineage,
    create_derived_artifact,
    is_sensitive_artifact,
    is_sensitive_label,
    propagate_labels,
    trace_lineage,
)


def test_customer_pii_is_sensitive():
    assert (
        is_sensitive_label(
            "CustomerPII"
        )
        is True
    )


def test_derived_customer_pii_is_sensitive():
    assert (
        is_sensitive_label(
            "DerivedFrom<CustomerPII>"
        )
        is True
    )


def test_public_label_is_not_sensitive():
    assert (
        is_sensitive_label(
            "PUBLIC"
        )
        is False
    )


def test_summary_preserves_customer_pii_lineage():
    customer_record = DataArtifact(
        artifact_id="artifact-customer-001",
        value={
            "name": "Demo Customer",
            "email": "demo@example.test",
        },
        labels={
            "CustomerPII",
        },
        parent_artifact_ids=set(),
        transformation=None,
    )

    summary = create_derived_artifact(
        artifact_id="artifact-summary-001",
        value="Customer invoice summary",
        parent_artifacts=[
            customer_record,
        ],
        transformation="summarizer",
    )

    assert (
        "DerivedFrom<CustomerPII>"
        in summary.labels
    )

    assert (
        "artifact-customer-001"
        in summary.parent_artifact_ids
    )

    assert (
        summary.transformation
        == "summarizer"
    )

    assert (
        contains_sensitive_lineage(
            summary
        )
        is True
    )


def test_public_data_remains_public():
    public_document = DataArtifact(
        artifact_id="artifact-public-001",
        value="Public information",
        labels={
            "PUBLIC",
        },
        parent_artifact_ids=set(),
        transformation=None,
    )

    labels = propagate_labels(
        [public_document]
    )

    assert labels == {
        "PUBLIC",
    }


def test_sensitive_artifact_detection():
    artifact = DataArtifact(
        artifact_id="artifact-secret-001",
        value="secret",
        labels={
            "SECRET",
        },
        parent_artifact_ids=set(),
        transformation=None,
    )

    assert (
        is_sensitive_artifact(
            artifact
        )
        is True
    )


def test_trace_lineage():
    customer = DataArtifact(
        artifact_id="customer",
        value="customer record",
        labels={
            "CustomerPII",
        },
        parent_artifact_ids=set(),
        transformation=None,
    )

    summary = DataArtifact(
        artifact_id="summary",
        value="summary",
        labels={
            "DerivedFrom<CustomerPII>",
        },
        parent_artifact_ids={
            "customer",
        },
        transformation="summarizer",
    )

    external_payload = DataArtifact(
        artifact_id="payload",
        value="payload",
        labels={
            "DerivedFrom<CustomerPII>",
        },
        parent_artifact_ids={
            "summary",
        },
        transformation="http_payload",
    )

    result = trace_lineage(
        "payload",
        [
            customer,
            summary,
            external_payload,
        ],
    )

    assert result == [
        "customer",
        "summary",
        "payload",
    ]