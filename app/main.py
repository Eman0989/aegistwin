from fastapi import FastAPI

from app.security.replay import run_attack_repair_replay

app = FastAPI(title="AegisTwin MVP", version="1.0.0")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "contract": "v1.0"}


@app.post("/attack-my-agent")
async def attack_my_agent() -> dict:
    result = await run_attack_repair_replay()
    return {
        key: value.model_dump(mode="json") if hasattr(value, "model_dump") else value
        for key, value in result.items()
    }
