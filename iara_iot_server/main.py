from __future__ import annotations

import asyncio
import json
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="Painel IoT Realtime")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

devices: dict[str, dict[str, Any]] = {
    "esp32c6": {
        "device": "esp32c6",
        "device_public_id": "ESP32C6",
        "chip": "ESP32-C6",
        "counter": 0,
        "value": 0.0,
        "temp_c": None,
        "tds_ppm": 0.0,
        "uptime_ms": 0,
        "project": "maedagua",
        "protocol": "iara.v1.telemetry",
        "privacy": "impersonal",
        "hub": {"queue_size": 0, "last_ack": {}},
        "ts": time.time(),
    }
}
logs_by_device: dict[str, deque[dict[str, Any]]] = defaultdict(lambda: deque(maxlen=500))
commands_by_device: dict[str, list[dict[str, Any]]] = defaultdict(list)
last_ack_by_device: dict[str, dict[str, Any]] = defaultdict(dict)
view_clients: set[WebSocket] = set()
clients_lock = asyncio.Lock()
next_command_id = 1


def _default_device_state(device: str) -> dict[str, Any]:
    return {
        "device": device,
        "device_public_id": device.upper(),
        "chip": "unknown",
        "counter": 0,
        "value": 0.0,
        "temp_c": None,
        "tds_ppm": 0.0,
        "uptime_ms": 0,
        "project": "maedagua",
        "protocol": "iara.v1.telemetry",
        "privacy": "impersonal",
        "hub": {
            "queue_size": 0,
            "last_ack": {},
        },
        "ts": time.time(),
    }


@app.get("/")
async def root() -> FileResponse:
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/device/{device_id}")
async def device_dashboard(device_id: str) -> FileResponse:
    return FileResponse(str(STATIC_DIR / "device.html"))


async def _broadcast_to_viewers(payload: dict[str, Any]) -> None:
    text = json.dumps(payload)

    async with clients_lock:
        clients = list(view_clients)

    stale: list[WebSocket] = []
    for ws in clients:
        try:
            await ws.send_text(text)
        except Exception:
            stale.append(ws)

    if stale:
        async with clients_lock:
            for ws in stale:
                view_clients.discard(ws)


def _normalize_device(raw: Any) -> str:
    if isinstance(raw, str) and raw.strip():
        return raw.strip().lower()
    return "esp32c6"


def _append_log(device: str, event: str, payload: dict[str, Any]) -> None:
    logs_by_device[device].append(
        {
            "ts": time.time(),
            "event": event,
            "payload": payload,
        }
    )


def _hub_snapshot(device: str) -> dict[str, Any]:
    queue = commands_by_device.get(device, [])
    pending = sum(1 for item in queue if item.get("status") in {"pending", "sent"})
    return {
        "queue_size": pending,
        "last_ack": last_ack_by_device.get(device, {}),
    }


def _ensure_device(device: str) -> dict[str, Any]:
    if device not in devices:
        devices[device] = _default_device_state(device)
    return devices[device]


def _refresh_hub_for_device(device: str) -> None:
    state = _ensure_device(device)
    state["hub"] = _hub_snapshot(device)


@app.post("/api/telemetry")
async def telemetry(request: Request) -> JSONResponse:
    payload = await request.json()
    if not isinstance(payload, dict):
        return JSONResponse({"ok": False, "error": "JSON inválido"}, status_code=400)

    device = _normalize_device(payload.get("device"))
    payload["device"] = device
    payload.setdefault("ts", time.time())
    payload.setdefault("protocol", "iara.v1.telemetry")
    payload.setdefault("project", "maedagua")
    payload.setdefault("privacy", "impersonal")
    payload.setdefault("device_public_id", device.upper())
    payload["hub"] = _hub_snapshot(device)
    devices[device] = payload
    _append_log(device, "telemetry", payload)

    await _broadcast_to_viewers(payload)

    return JSONResponse({"ok": True})


@app.get("/api/telemetry/all")
async def telemetry_all() -> JSONResponse:
    return JSONResponse({"ok": True, "devices": devices})


@app.get("/api/devices")
async def list_devices() -> JSONResponse:
    rows: list[dict[str, Any]] = []
    now = time.time()
    for device, data in devices.items():
        ts = float(data.get("ts", 0) or 0)
        rows.append(
            {
                "device": device,
                "device_public_id": data.get("device_public_id", device.upper()),
                "chip": data.get("chip", "unknown"),
                "model": data.get("model", "unknown"),
                "project": data.get("project", "maedagua"),
                "protocol": data.get("protocol", "iara.v1.telemetry"),
                "last_seen_s": max(0, int(now - ts)) if ts else None,
                "status": "online" if ts and now - ts < 15 else "offline",
                "temp_c": data.get("temp_c"),
                "tds_ppm": data.get("tds_ppm", data.get("value")),
            }
        )

    rows.sort(key=lambda d: d["device"])
    return JSONResponse({"ok": True, "devices": rows})


@app.get("/api/device/{device_id}/state")
async def device_state(device_id: str) -> JSONResponse:
    device = _normalize_device(device_id)
    if device not in devices:
        return JSONResponse({"ok": False, "error": "Device não encontrado"}, status_code=404)

    return JSONResponse(
        {
            "ok": True,
            "device": devices[device],
            "logs": list(logs_by_device[device])[-120:],
        }
    )


@app.get("/api/device/{device_id}/logs")
async def device_logs_route(device_id: str, limit: int = 120) -> JSONResponse:
    device = _normalize_device(device_id)
    if device not in devices:
        return JSONResponse({"ok": False, "error": "Device não encontrado"}, status_code=404)

    safe_limit = max(1, min(limit, 500))
    return JSONResponse({"ok": True, "logs": list(logs_by_device[device])[-safe_limit:]})


@app.post("/api/ui/command")
async def queue_command(request: Request) -> JSONResponse:
    global next_command_id

    payload = await request.json()
    if not isinstance(payload, dict):
        return JSONResponse({"ok": False, "error": "JSON inválido"}, status_code=400)

    action = payload.get("action")
    if not isinstance(action, str) or not action.strip():
        return JSONResponse({"ok": False, "error": "Campo action é obrigatório"}, status_code=400)

    device = _normalize_device(payload.get("device"))
    command = {
        "id": next_command_id,
        "device": device,
        "action": action.strip(),
        "value": payload.get("value"),
        "status": "pending",
        "created_at": time.time(),
    }
    next_command_id += 1

    queue = commands_by_device[device]
    queue.append(command)
    if len(queue) > 120:
        commands_by_device[device] = queue[-120:]

    _refresh_hub_for_device(device)
    _append_log(device, "command_queued", command)
    await _broadcast_to_viewers(devices[device])

    return JSONResponse({"ok": True, "command": command})


@app.get("/api/device/command")
async def pull_command(device: str = "esp32c6") -> JSONResponse:
    normalized = _normalize_device(device)
    queue = commands_by_device[normalized]

    for cmd in queue:
        if cmd.get("status") in {"pending", "sent"}:
            cmd["status"] = "sent"
            cmd["sent_at"] = time.time()
            return JSONResponse({"ok": True, "command": cmd})

    return JSONResponse({"ok": True, "command": None})


@app.post("/api/device/ack")
async def ack_command(request: Request) -> JSONResponse:
    payload = await request.json()
    if not isinstance(payload, dict):
        return JSONResponse({"ok": False, "error": "JSON inválido"}, status_code=400)

    device = _normalize_device(payload.get("device"))
    command_id = payload.get("command_id")
    status = payload.get("status", "ok")
    message = payload.get("message", "")

    queue = commands_by_device[device]
    target: dict[str, Any] | None = None
    for cmd in queue:
        if cmd.get("id") == command_id:
            target = cmd
            break

    if target is None:
        return JSONResponse({"ok": False, "error": "Comando não encontrado"}, status_code=404)

    target["status"] = "ack"
    target["ack_status"] = status
    target["ack_message"] = message
    target["ack_at"] = time.time()

    if len(queue) > 60:
        commands_by_device[device] = queue[-60:]

    last_ack_by_device[device] = {
        "command_id": command_id,
        "status": status,
        "message": message,
        "ts": time.time(),
    }

    _refresh_hub_for_device(device)
    _append_log(
        device,
        "command_ack",
        {
            "command_id": command_id,
            "status": status,
            "message": message,
        },
    )
    await _broadcast_to_viewers(devices[device])

    return JSONResponse({"ok": True})


@app.websocket("/ws/view")
async def ws_view(websocket: WebSocket) -> None:
    await websocket.accept()

    async with clients_lock:
        view_clients.add(websocket)

    try:
        if devices:
            newest = max(devices.values(), key=lambda d: float(d.get("ts", 0) or 0))
            await websocket.send_json(newest)
        else:
            await websocket.send_json(_default_device_state("esp32c6"))

        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        async with clients_lock:
            view_clients.discard(websocket)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
