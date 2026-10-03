"""Frozen MVP configuration."""

SENSITIVE_LABELS = {"CustomerPII", "DerivedFrom<CustomerPII>"}
EXTERNAL_DESTINATION = "EXTERNAL"
MVP_TOOLS = {
    "invoice_reader",
    "customer_database",
    "summarizer",
    "external_http",
}
