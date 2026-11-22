"""Radar panel for the dashboard: the LIDAR monitor's state file -> what the radar draws.

The dashboard never opens the LIDAR's port (the `forrest-lidar` service holds
it). It reads $XDG_RUNTIME_DIR/forrest/lidar.json, which the monitor replaces
5 times a second. Pure except for reading the file, so it is tested without a LIDAR.

  running  scanning, and the file is fresh (newer than STALE_S)
  error    the monitor says why (unplugged, timed out, ...)
  stopped  no file, or an old one: the monitor isn't running
"""

from __future__ import annotations

from typing import Optional

STALE_S = 3.0        # the monitor writes every 0.2 s; 3 s without = not running


def panel(snap: Optional[dict], now: float) -> dict:
    """-> {"running": bool, "state": "running"|"error"|"stopped", "error": text|None,
           "rate_hz", "points", "bin_deg", "bins", "sectors", "device", "age_s"}"""
    if snap is None or now - snap.get("updated", 0) > STALE_S:
        why = ("LIDAR monitor not running · systemctl --user start forrest-lidar" if snap is None
               else f"LIDAR monitor stopped (last update {now - snap['updated']:.0f} s ago)")
        return {"running": False, "state": "stopped", "error": why, "bins": None,
                "device": (snap or {}).get("device")}
    out = {k: snap.get(k) for k in ("rate_hz", "points", "bin_deg", "bins", "sectors", "device")}
    out["age_s"] = round(now - snap["updated"], 2)
    if snap.get("link") == "up" and snap.get("bins") is not None:
        return {**out, "running": True, "state": "running", "error": None}
    return {**out, "running": False, "state": "error", "bins": None,
            "error": f"LIDAR: {snap.get('error') or 'not scanning'}"}
