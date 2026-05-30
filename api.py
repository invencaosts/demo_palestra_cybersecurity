# dependencies: fastapi uvicorn

import asyncio
import random
import uuid
from datetime import datetime, timezone
from typing import Optional

import uvicorn
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="CyberDemo API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

log_queue: list[dict] = []

system_state: dict = {
    "estado": "NORMAL",
    "ip_bloqueado": None,
    "mensagem": "",
}

# Modelo Qwen (LM Studio) armazenado em memória (definido pelo controle.py)
qwen_model: str = "qwen/qwen3-4b-thinking-2507"

FAKE_IPS = [
    "203.0.113.5",  "198.51.100.22", "192.0.2.17",    "45.33.32.156",
    "104.21.14.99", "172.67.68.228", "34.102.136.180", "23.227.38.65",
    "151.101.1.69", "151.101.65.69", "185.199.108.153","140.82.121.4",
    "192.30.255.112","13.107.42.14", "20.112.52.29",   "52.96.138.2",
    "216.58.206.46", "142.250.80.46","74.125.24.138",  "66.102.9.104",
]

ENDPOINTS = ["/home", "/api/data", "/dashboard", "/profile"]
METHODS   = ["GET", "POST"]


def _make_log(ip: str, method: str, endpoint: str, status_code: int, tipo: str) -> dict:
    return {
        "id":              str(uuid.uuid4()),
        "timestamp":       datetime.now(timezone.utc).isoformat(),
        "ip":              ip,
        "method":          method,
        "endpoint":        endpoint,
        "status_code":     status_code,
        "response_time_ms": random.randint(50, 300),
        "tipo":            tipo,
    }


def _push(log: dict) -> None:
    log_queue.append(log)
    if len(log_queue) > 200:
        del log_queue[:-200]


async def background_logger() -> None:
    while True:
        await asyncio.sleep(2)
        ip       = random.choice(FAKE_IPS)
        method   = random.choice(METHODS)
        endpoint = random.choice(ENDPOINTS)
        status   = 200 if random.random() < 0.8 else 404
        _push(_make_log(ip, method, endpoint, status, "normal"))


@app.on_event("startup")
async def startup_event() -> None:
    asyncio.create_task(background_logger())


@app.get("/logs")
def get_logs() -> list[dict]:
    return log_queue[-50:]


@app.get("/status")
def get_status() -> dict:
    return system_state


# ── Modelo Qwen gerenciado pela API ─────────────────────────────────────────
@app.get("/set-qwen-model")
def set_qwen_model(model: str = Query(...)) -> dict:
    global qwen_model
    qwen_model = model
    return {"ok": True}


@app.get("/get-qwen-model")
def get_qwen_model() -> dict:
    return {"model": qwen_model}


# ── Estado definido pela IA ─────────────────────────────────────────────────
@app.get("/set-state")
def set_state(
    estado:   str            = Query(...),
    ip:       Optional[str]  = Query(None),
    mensagem: str            = Query(""),
) -> dict:
    system_state["estado"]      = estado
    system_state["ip_bloqueado"] = ip or None
    system_state["mensagem"]    = mensagem
    return {"ok": True}


# ── Simulações — apenas injetam logs, NÃO alteram system_state ─────────────
@app.get("/attack")
def simulate_attack() -> dict:
    attacker_ip = "185.220.101.45"
    for _ in range(50):
        _push(_make_log(attacker_ip, "POST", "/admin/login", 401, "ataque"))
    return {"injected": 50, "ip": attacker_ip}


@app.get("/false-positive")
async def simulate_false_positive() -> dict:
    human_ip = "192.168.1.10"
    for _ in range(3):
        _push(_make_log(human_ip, "POST", "/login", 401, "falso_positivo"))
        await asyncio.sleep(2)
    return {"injected": 3, "ip": human_ip}


@app.get("/reset")
def reset_logs() -> dict:
    log_queue.clear()
    system_state["estado"]       = "NORMAL"
    system_state["ip_bloqueado"] = None
    system_state["mensagem"]     = ""
    return {"status": "cleared"}


if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=False)