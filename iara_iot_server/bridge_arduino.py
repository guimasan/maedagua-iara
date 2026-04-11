from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any
from urllib import parse, request

import serial


def load_env_file(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _coerce(raw: str) -> Any:
    value = raw.strip()
    if value.upper() == "NAN":
        return None
    if value.lower() in {"true", "false"}:
        return value.lower() == "true"
    try:
        if any(ch in value for ch in [".", "e", "E"]):
            return float(value)
        return int(value)
    except Exception:
        return value


def _parse_kv_line(line: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for part in [p.strip() for p in line.split(";") if p.strip()]:
        if "=" not in part:
            continue
        k, v = part.split("=", 1)
        out[k.strip().lower()] = _coerce(v)
    return out


def parse_uno_line(line: str) -> dict[str, Any] | None:
    parts = [p.strip() for p in line.split(";") if p.strip()]
    if not parts:
        return None

    header = parts[0].upper()

    if header == "IARA_HELLO":
        kv = _parse_kv_line(";".join(parts[1:]))
        device_public_id = kv.get("device_public_id")
        if not isinstance(device_public_id, str) or not device_public_id:
            return None

        modules_raw = kv.get("modules", "")
        modules = [m.strip() for m in str(modules_raw).split(",") if m.strip()]

        return {
            "kind": "hello",
            "project": str(kv.get("project", "maedagua")),
            "protocol": str(kv.get("protocol", "iara.v1")),
            "device_public_id": device_public_id,
            "model": str(kv.get("model", "iara_v1_uno")),
            "fw": str(kv.get("fw", "1.0.0")),
            "modules": modules,
        }

    if header == "IARA_TLM":
        kv = _parse_kv_line(";".join(parts[1:]))
        device_public_id = kv.get("device_public_id")
        if not isinstance(device_public_id, str) or not device_public_id:
            return None

        temp_c = kv.get("temp_c") if isinstance(kv.get("temp_c"), (int, float)) or kv.get("temp_c") is None else None
        tds_ppm = float(kv.get("tds_ppm", 0) or 0)
        a1_v = float(kv.get("a1_v", 0) or 0)

        return {
            "kind": "telemetry",
            "project": str(kv.get("project", "maedagua")),
            "protocol": str(kv.get("protocol", "iara.v1")),
            "device_public_id": device_public_id,
            "temp_c": temp_c,
            "tds_ppm": tds_ppm,
            "a1_v": a1_v,
            "ts_ms": int(kv.get("ts_ms", 0) or 0),
            "fields": kv,
        }

    kv = _parse_kv_line(line)
    if "temp_c" not in kv and "tds_ppm" not in kv and "device" not in kv:
        return None

    device_public_id = str(kv.get("device", "iara-uno-0001"))
    temp_raw = kv.get("temp_c")
    temp_c = temp_raw if isinstance(temp_raw, (int, float)) or temp_raw is None else None
    tds_ppm = float(kv.get("tds_ppm", 0) or 0)
    a1_v = float(kv.get("a1_v", kv.get("tds_v", 0)) or 0)

    return {
        "kind": "telemetry",
        "project": str(kv.get("project", "maedagua")),
        "protocol": str(kv.get("protocol", "iara.v1")),
        "device_public_id": device_public_id,
        "temp_c": temp_c,
        "tds_ppm": tds_ppm,
        "a1_v": a1_v,
        "fields": kv,
    }


def post_payload(url: str, payload: dict[str, Any]) -> int:
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=4) as resp:
        return resp.status


def pull_command(base_url: str, device: str) -> dict[str, Any] | None:
    url = f"{base_url.rstrip('/')}/api/device/command?{parse.urlencode({'device': device.lower()})}"
    with request.urlopen(url, timeout=4) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if not data.get("ok"):
        return None
    cmd = data.get("command")
    if not isinstance(cmd, dict):
        return None
    return cmd


def ack_command(base_url: str, device: str, command_id: int, status: str, message: str) -> None:
    payload = {
        "device": device.lower(),
        "command_id": command_id,
        "status": status,
        "message": message,
    }
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        f"{base_url.rstrip('/')}/api/device/ack",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=4):
        pass


def map_action_to_serial(action: str, value: Any, ec_to_ppm_factor: float) -> str | None:
    action = (action or "").strip().lower()

    if action == "serial_cmd" and isinstance(value, str) and value.strip():
        return value.strip()
    if action == "cal_on":
        return "CAL=ON"
    if action == "cal_off":
        return "CAL=OFF"
    if action == "cal_save":
        return "CAL=SAVE"
    if action == "cal_reset":
        return "CAL=RESET"
    if action == "cal_status":
        return "CAL?"
    if action == "set_read_mode":
        return f"MODE={int(value)}"
    if action == "set_display_mode":
        return f"DISP={int(value)}"
    if action == "cal_apply_ppm":
        try:
            ppm = float(value)
            return f"CAL=APPLY:{ppm:.2f}"
        except Exception:
            return None
    if action == "cal_apply_uscm":
        try:
            us_cm = float(value["us_cm"] if isinstance(value, dict) else value)
            factor = float(value.get("factor", ec_to_ppm_factor)) if isinstance(value, dict) else ec_to_ppm_factor
            ppm = us_cm * factor
            return f"CAL=APPLY:{ppm:.2f}"
        except Exception:
            return None
    if action == "cal_apply_1413":
        ppm = 1413.0 * ec_to_ppm_factor
        return f"CAL=APPLY:{ppm:.2f}"

    return None


def telemetry_base_url(full_telemetry_url: str) -> str:
    marker = "/api/telemetry"
    if marker in full_telemetry_url:
        return full_telemetry_url.split(marker, 1)[0]
    return full_telemetry_url.rstrip("/")


def build_hello_payload(identity: dict[str, Any], counter: int) -> dict[str, Any]:
    return {
        "device": str(identity["device_public_id"]).lower(),
        "device_public_id": identity["device_public_id"],
        "project": identity["project"],
        "protocol": identity["protocol"],
        "chip": "Arduino Uno",
        "model": identity["model"],
        "fw_version": identity["fw"],
        "modules": identity["modules"],
        "counter": counter,
        "value": 0.0,
        "temp_c": None,
        "tds_ppm": 0,
        "privacy": "impersonal",
        "integration": "independent",
        "event": "hello",
        "ts": time.time(),
    }


def build_telemetry_payload(identity: dict[str, Any], parsed: dict[str, Any], counter: int) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "device": str(identity["device_public_id"]).lower(),
        "device_public_id": identity["device_public_id"],
        "project": parsed.get("project", identity["project"]),
        "protocol": parsed.get("protocol", identity["protocol"]),
        "chip": "Arduino Uno",
        "model": identity["model"],
        "fw_version": identity["fw"],
        "modules": identity["modules"],
        "counter": counter,
        "value": parsed.get("tds_ppm", 0),
        "temp_c": parsed.get("temp_c"),
        "tds_ppm": parsed.get("tds_ppm", 0),
        "a1_v": parsed.get("a1_v", 0),
        "privacy": "impersonal",
        "integration": "independent",
        "event": "telemetry",
        "ts": time.time(),
    }

    fields = parsed.get("fields") if isinstance(parsed, dict) else None
    if isinstance(fields, dict):
        payload["vars"] = fields

        reserved = {
            "device",
            "device_public_id",
            "project",
            "protocol",
            "chip",
            "model",
            "fw",
            "fw_version",
            "modules",
            "counter",
            "value",
            "temp_c",
            "tds_ppm",
            "a1_v",
            "privacy",
            "integration",
            "event",
            "ts",
        }
        for k, v in fields.items():
            if k not in reserved:
                payload[k] = v

        if isinstance(fields.get("ts_ms"), (int, float)):
            payload["uptime_ms"] = int(fields["ts_ms"])
        if isinstance(fields.get("tds_v"), (int, float)):
            payload["a1_v"] = float(fields["tds_v"])

    return payload


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    load_env_file(root / ".env")

    server_url = os.getenv("ONLINE_SERVER_URL", "http://127.0.0.1:8000/api/telemetry")
    server_base = telemetry_base_url(server_url)
    serial_port = os.getenv("SERIAL_PORT", "/dev/ttyUSB0")
    baud = int(os.getenv("SERIAL_BAUD", "115200"))
    interval_ms = int(os.getenv("POST_INTERVAL_MS", "1000"))
    command_poll_ms = int(os.getenv("COMMAND_POLL_MS", "1200"))
    ec_to_ppm_factor = float(os.getenv("EC_TO_PPM_FACTOR", "0.5"))

    default_public_id = os.getenv("DEVICE_PUBLIC_ID", "iara-uno-0001")
    default_model = os.getenv("DEVICE_MODEL", "iara_v1_uno")
    default_fw = os.getenv("FIRMWARE_VERSION", "1.0.0")
    default_modules = [m.strip() for m in os.getenv("MODULES", "temp_ds18b20,tds_keyestudio_v1,oled_ssd1306").split(",") if m.strip()]
    default_project = os.getenv("PROJECT_CODE", "maedagua")
    default_protocol = os.getenv("PROTOCOL_VERSION", "iara.v1")

    print(f"[bridge] Porta serial: {serial_port} @ {baud}")
    print(f"[bridge] Enviando para: {server_url}")
    print(f"[bridge] Fator EC->PPM: {ec_to_ppm_factor}")

    counter = 0
    last_post_ms = 0
    identity: dict[str, Any] = {
        "device_public_id": default_public_id,
        "model": default_model,
        "fw": default_fw,
        "modules": default_modules,
        "project": default_project,
        "protocol": default_protocol,
    }

    while True:
        try:
            with serial.Serial(serial_port, baudrate=baud, timeout=1) as ser:
                print("[bridge] Serial aberta")
                last_command_poll = 0

                while True:
                    now_loop_ms = int(time.time() * 1000)
                    if now_loop_ms - last_command_poll >= command_poll_ms:
                        last_command_poll = now_loop_ms
                        try:
                            cmd = pull_command(server_base, identity["device_public_id"])
                            if cmd:
                                command_id = cmd.get("id")
                                if not isinstance(command_id, int):
                                    try:
                                        command_id = int(command_id)
                                    except Exception:
                                        command_id = None

                                serial_cmd = map_action_to_serial(str(cmd.get("action", "")), cmd.get("value"), ec_to_ppm_factor)
                                if serial_cmd and command_id is not None:
                                    ser.write((serial_cmd + "\n").encode("utf-8"))
                                    ser.flush()
                                    ack_command(server_base, identity["device_public_id"], command_id, "ok", f"serial:{serial_cmd}")
                                    print(f"[bridge] CMD #{command_id} -> {serial_cmd}")
                                elif command_id is not None:
                                    ack_command(server_base, identity["device_public_id"], command_id, "error", "acao_nao_suportada")
                        except Exception as exc:
                            print(f"[bridge] erro ao processar comando do hub: {exc}")

                    raw = ser.readline().decode("utf-8", errors="ignore").strip()
                    if not raw:
                        continue

                    parsed = parse_uno_line(raw)
                    if parsed is None:
                        continue

                    kind = parsed.get("kind", "telemetry")

                    if kind == "hello":
                        identity.update(
                            {
                                "device_public_id": parsed.get("device_public_id", identity["device_public_id"]),
                                "model": parsed.get("model", identity["model"]),
                                "fw": parsed.get("fw", identity["fw"]),
                                "modules": parsed.get("modules", identity["modules"]),
                                "project": parsed.get("project", identity["project"]),
                                "protocol": parsed.get("protocol", identity["protocol"]),
                            }
                        )

                        hello_payload = build_hello_payload(identity, counter)

                        try:
                            status = post_payload(server_url, hello_payload)
                            print(f"[bridge] HELLO POST {status} id={hello_payload['device_public_id']}")
                        except Exception as exc:
                            print(f"[bridge] erro ao enviar hello: {exc}")
                        continue

                    now_ms = int(time.time() * 1000)
                    if now_ms - last_post_ms < interval_ms:
                        continue
                    last_post_ms = now_ms

                    counter += 1
                    payload = build_telemetry_payload(identity, parsed, counter)

                    try:
                        status = post_payload(server_url, payload)
                        print(f"[bridge] POST {status} temp={payload['temp_c']}C tds={payload['tds_ppm']}ppm")
                    except Exception as exc:
                        print(f"[bridge] erro ao enviar: {exc}")

        except serial.SerialException as exc:
            print(f"[bridge] serial indisponível ({exc}), tentando reconectar em 2s...")
            time.sleep(2)
        except Exception as exc:
            print(f"[bridge] erro inesperado ({exc}), reiniciando loop em 2s...")
            time.sleep(2)


if __name__ == "__main__":
    main()
