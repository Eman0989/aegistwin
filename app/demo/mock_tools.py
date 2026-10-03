"""Safe in-process mock tools for the canonical demo."""

from typing import Any

from app.contracts import DataArtifact, ObservedEffect, ToolCall
from app.demo.fixtures import EXTERNAL_ENDPOINT, FAKE_CUSTOMER, FAKE_INVOICE, MALICIOUS_WEBPAGE


def invoice_reader(call: ToolCall) -> tuple[list[DataArtifact], list[ObservedEffect]]:
    malicious = bool(call.arguments.get("malicious", False))
    payload: dict[str, Any] = {
        "invoice": FAKE_INVOICE,
        "source": MALICIOUS_WEBPAGE if malicious else {"content": FAKE_INVOICE["content"]},
    }
    labels = {"INTERNAL"}
    if malicious:
        labels.add("UNTRUSTED")
    artifact = DataArtifact(
        artifact_id=f"artifact-{call.call_id}",
        value=payload,
        labels=labels,
        transformation="invoice_read",
    )
    effect = ObservedEffect(
        effect_type="READ_INVOICE",
        resource=FAKE_INVOICE["invoice_id"],
        data_labels=labels,
    )
    return [artifact], [effect]


def customer_database(call: ToolCall) -> tuple[list[DataArtifact], list[ObservedEffect]]:
    artifact = DataArtifact(
        artifact_id=f"artifact-{call.call_id}",
        value=FAKE_CUSTOMER,
        labels={"CustomerPII"},
        transformation="database_read",
    )
    effect = ObservedEffect(
        effect_type="READ_CUSTOMER_PII",
        resource="customer_database",
        data_labels={"CustomerPII"},
    )
    return [artifact], [effect]


def summarizer(
    call: ToolCall, inputs: list[DataArtifact]
) -> tuple[list[DataArtifact], list[ObservedEffect]]:
    parent_labels = set().union(*(a.labels for a in inputs)) if inputs else set()
    output_labels = set(parent_labels)
    if "CustomerPII" in parent_labels or "DerivedFrom<CustomerPII>" in parent_labels:
        output_labels.discard("CustomerPII")
        output_labels.add("DerivedFrom<CustomerPII>")
    artifact = DataArtifact(
        artifact_id=f"artifact-{call.call_id}",
        value="Summary of supplied invoice and customer information.",
        labels=output_labels,
        parent_artifact_ids=[a.artifact_id for a in inputs],
        transformation="summarize",
    )
    effect = ObservedEffect(
        effect_type="TRANSFORM_DATA",
        resource="summary",
        data_labels=output_labels,
    )
    return [artifact], [effect]


def external_http(
    call: ToolCall, inputs: list[DataArtifact]
) -> tuple[list[DataArtifact], list[ObservedEffect]]:
    labels = set().union(*(a.labels for a in inputs)) if inputs else set()
    effect = ObservedEffect(
        effect_type="EXTERNAL_NETWORK",
        destination="EXTERNAL",
        data_labels=labels,
        metadata={"endpoint": EXTERNAL_ENDPOINT},
    )
    artifact = DataArtifact(
        artifact_id=f"artifact-{call.call_id}",
        value={"status": "simulated_sent", "endpoint": EXTERNAL_ENDPOINT},
        labels={"PUBLIC"},
        parent_artifact_ids=[a.artifact_id for a in inputs],
        transformation="external_send",
    )
    return [artifact], [effect]


TOOL_FUNCTIONS = {
    "invoice_reader": invoice_reader,
    "customer_database": customer_database,
    "summarizer": summarizer,
    "external_http": external_http,
}

DECLARED_EFFECTS = {
    "invoice_reader": ["READ_INVOICE"],
    "customer_database": ["READ_CUSTOMER_PII"],
    "summarizer": ["TRANSFORM_DATA"],
    "external_http": ["EXTERNAL_NETWORK"],
}
