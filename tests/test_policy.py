from app.contracts import AttackPath, InstructionOrigin, RiskLevel
from app.security.compiler import compile_guardrail


def test_compiler_creates_narrow_external_data_guardrail():
    attack = AttackPath(
        attack_id="ATK-001",
        original_intent="Summarize invoice",
        instruction_origin=InstructionOrigin.WEB_UNTRUSTED,
        path=["customer_database", "summarizer", "external_http"],
        final_effect="External data transfer",
        source_labels={"CustomerPII", "DerivedFrom<CustomerPII>"},
        destination="EXTERNAL",
        risk_level=RiskLevel.CRITICAL,
    )
    guardrail = compile_guardrail(attack)
    assert guardrail.destination == "EXTERNAL"
    assert "DerivedFrom<CustomerPII>" in guardrail.source_labels
    assert guardrail.generated_from_attack == "ATK-001"
