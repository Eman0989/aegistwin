# AegisTwin Backend MVP

A lightweight HackYeah demonstration of the AegisTwin attack-to-guardrail loop.

## What is implemented

- Frozen Shared Contract v1.0
- Four synthetic MVP tools
- Normalized tool calls and effect receipts
- Sensitive-data lineage through summarization
- Deterministic policy enforcement
- Guardrail compilation from a verified attack path
- Attack replay and legitimate-workflow regression test
- `POST /attack-my-agent` demo endpoint

The `app/twin/` package is intentionally reserved for the Twin Intelligence branch.

## Run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Then call:

```bash
curl -X POST http://127.0.0.1:8000/attack-my-agent
```

## Test

```bash
pytest
```
