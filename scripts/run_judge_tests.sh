#!/usr/bin/env bash

set -euo pipefail

echo
echo "AEGISTWIN — JUDGE TEST SUITE"
echo "============================================"

echo
echo "1. Running automated positive and negative tests..."
python -m pytest -q

echo
echo "2. Validating model-driven benchmark scenarios..."

python - <<'PY'
from collections import Counter

from app.security.agent_benchmark import (
    load_benchmark_scenarios,
)

scenarios = load_benchmark_scenarios()

kinds = Counter(
    scenario.kind.value
    for scenario in scenarios
)

scenario_ids = [
    scenario.scenario_id
    for scenario in scenarios
]

categories = {
    scenario.category
    for scenario in scenarios
}

print("TOTAL CASES:", len(scenarios))
print("ATTACK CASES:", kinds["attack"])
print("LEGITIMATE CASES:", kinds["legitimate"])
print("SECURITY CATEGORIES:", len(categories))
print("UNIQUE IDS:", len(set(scenario_ids)))

assert len(scenarios) == 75
assert kinds["attack"] == 50
assert kinds["legitimate"] == 25
assert len(scenario_ids) == len(set(scenario_ids))

print("SCENARIO VALIDATION: PASSED")
PY

echo
echo "============================================"
echo "AEGISTWIN JUDGE TEST SUITE: PASSED"
echo "============================================"