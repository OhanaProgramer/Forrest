"""Sensor panel for the dashboard: the sensor monitor's state file -> sidebar
inputs and the Sensor Pico tile.

The dashboard never opens the sensor Pico's port (`forrest-sensors` holds it).
It reads $XDG_RUNTIME_DIR/forrest/sensors.json. Pure, so it's tested without
hardware. A reading is only shown while it's fresh: an old number that looks
live is worse than a dash.
"""

from __future__ import annotations

from typing import Optional

STALE_STATE_S = 5.0     # monitor writes every 0.5 s
STALE_ENV_S = 15.0      # BME688 every 5 s
STALE_ACC_S = 5.0       # ACC summary every 1 s
EVENT_SHOW_S = 600      # flips / impacts stay in the sidebar for 10 min


def _age(s: float) -> str:
    return f"{s:.0f} s ago" if s < 90 else f"{s / 60:.0f} min ago"


def panel(snap: Optional[dict], now: float) -> dict:
    """-> {"env": dict|None, "env_why": text, "motion": dict|None, "motion_why": text,
           "tile": {...} (the Sensor Pico tile), "monitor": "running"|"stopped"}

    env:    {"temp_c", "humidity_pct", "pressure_hpa", "gas_ohm", "gas_low"}
    motion: {"face", "tilt_deg", "upside_down", "peak_g", "last_event": {what, v, ago_s}|None}
    """
    def tile(value, detail, lvl):
        return {"key": "pico_sensors", "title": "Sensor Pico", "value": value, "detail": detail,
                "level": lvl, "group": "pico", "source": "forrest-sensors monitor (JSON lines from the Pico W)"}

    if snap is None or now - snap.get("updated", 0) > STALE_STATE_S:
        why = "sensor monitor not running · systemctl --user start forrest-sensors"
        return {"env": None, "env_why": why, "motion": None, "motion_why": why,
                "tile": tile("no monitor", why, "warn"), "monitor": "stopped"}

    if snap.get("link") != "up":
        why = f"sensor Pico: {snap.get('error') or snap.get('link')}"
        return {"env": None, "env_why": why, "motion": None, "motion_why": why,
                "tile": tile("not connected", snap.get("error") or "", "warn"), "monitor": "running"}

    env, env_why = None, ""
    e = snap.get("env")
    if snap.get("env_err"):
        env_why = f"BME688: {snap['env_err']}"
    elif e is None:
        env_why = "waiting for the first reading"
    elif now - e.get("at", 0) > STALE_ENV_S:
        env_why = f"BME688 silent, last reading {_age(now - e['at'])}"
    else:
        env = {"temp_c": e["t"], "humidity_pct": e["rh"], "pressure_hpa": e["p"],
               "gas_ohm": e.get("gas"), "gas_low": bool(e.get("gas_low"))}

    motion, motion_why = None, ""
    a = snap.get("acc")
    if snap.get("acc_err"):
        motion_why = f"LIS3DH: {snap['acc_err']}"
    elif a is None:
        motion_why = "waiting for the first reading"
    elif now - a.get("at", 0) > STALE_ACC_S:
        motion_why = f"LIS3DH silent, last reading {_age(now - a['at'])}"
    else:
        recent = [ev for ev in snap.get("events") or [] if now - ev.get("at", 0) <= EVENT_SHOW_S]
        last = recent[-1] if recent else None
        motion = {"face": a.get("face"), "tilt_deg": a.get("tilt"), "upside_down": bool(a.get("down")),
                  "peak_g": a.get("peak"),
                  "last_event": None if last is None else
                  {"what": last["what"], "v": last.get("v"), "ago_s": now - last["at"]}}

    missing = [n for n, ok in (("BME688", env is not None), ("LIS3DH", motion is not None)) if not ok]
    # fw comes from READY, sent once at Pico boot: unknown if the monitor started later
    detail = "BME688 + LIS3DH" + (f" · {snap['fw']}" if snap.get("fw") else "") + \
             (f"\nnot reading: {', '.join(missing)}" if missing else "")
    return {"env": env, "env_why": env_why, "motion": motion, "motion_why": motion_why,
            "tile": tile("up" if not missing else "partial", detail, "ok" if not missing else "warn"),
            "monitor": "running"}
