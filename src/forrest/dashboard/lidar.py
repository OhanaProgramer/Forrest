"""Radar panel for the dashboard: the LIDAR monitor's state file -> what the radar draws.

The dashboard never opens the LIDAR's port (the `forrest-lidar` service holds
it). It reads $XDG_RUNTIME_DIR/forrest/lidar.json, which the monitor replaces
5 times a second. Pure except for reading the file, so it is tested without a LIDAR.

  running     scanning, and the file is fresh (newer than STALE_S)
  connecting  the monitor is opening the port / waiting for motor spin-up
  error       the monitor says why (unplugged, timed out, ...)
  stopped     no file, or an old one: the monitor isn't running

While it isn't running, the message says how long the LIDAR has been down,
as h / min / s (fmt_duration).
"""

from __future__ import annotations

from typing import Optional

STALE_S = 3.0        # the monitor writes every 0.2 s; 3 s without = not running
CONNECT_STALE_S = 8.0  # one quiet connect attempt: open + spin-up (up to 5 s) + margin


def fmt_duration(s: float) -> str:
    """19 s, 4 min 05 s, 1 h 02 min 05 s."""
    s = max(0, int(round(s)))
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    if h:
        return f"{h} h {m:02d} min {sec:02d} s"
    if m:
        return f"{m} min {sec:02d} s"
    return f"{sec} s"


def panel(snap: Optional[dict], now: float) -> dict:
    """-> {"running": bool, "state": "running"|"error"|"stopped", "error": text|None,
           "rate_hz", "points", "bin_deg", "bins", "sectors", "device", "age_s"}"""
    stale_s = CONNECT_STALE_S if snap and snap.get("link") == "connecting" else STALE_S
    if snap is None or now - snap.get("updated", 0) > stale_s:
        why = ("LIDAR monitor not running · systemctl --user start forrest-lidar" if snap is None
               else f"LIDAR monitor stopped (last update {fmt_duration(now - snap['updated'])} ago)")
        return {"running": False, "state": "stopped", "error": why, "bins": None,
                "device": (snap or {}).get("device"), "down_s": None}
    out = {k: snap.get(k) for k in ("rate_hz", "points", "bin_deg", "bins", "sectors", "device")}
    out["age_s"] = round(now - snap["updated"], 2)
    if snap.get("link") == "up" and snap.get("bins") is not None:
        return {**out, "running": True, "state": "running", "error": None, "down_s": None}
    ds = snap.get("down_since")
    down_s = round(now - ds, 1) if ds is not None else None
    down = f" · down {fmt_duration(down_s)}" if down_s is not None else ""
    if snap.get("link") == "connecting":
        last = f" (last error: {snap['error']})" if snap.get("error") else ""
        return {**out, "running": False, "state": "connecting", "bins": None, "down_s": down_s,
                "error": f"LIDAR connecting{down}{last}"}
    return {**out, "running": False, "state": "error", "bins": None, "down_s": down_s,
            "error": f"LIDAR: {snap.get('error') or 'not scanning'}{down}"}
