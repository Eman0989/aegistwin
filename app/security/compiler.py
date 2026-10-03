from app.contracts import AttackPath, DecisionAction, Guardrail


def compile_guardrail(attack: AttackPath) -> Guardrail:
    if attack.destination != "EXTERNAL" or not attack.source_labels:
        raise ValueError("MVP compiler only supports labelled data flowing to EXTERNAL")
    return Guardrail(
        guardrail_id=f"GR-{attack.attack_id}",
        source_labels=set(attack.source_labels),
        destination="EXTERNAL",
        action=DecisionAction.BLOCK,
        generated_from_attack=attack.attack_id,
        reason="Sensitive data or its derived content cannot cross the external trust boundary.",
    )
