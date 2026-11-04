"""Hardware status for the dashboard: Pi heat/power, load, memory, disk.

Parsers are pure functions so they test without a Pi; `read_status` does
the reading and returns None for anything not available on this machine.
"""

from __future__ import annotations

import shutil
import time
from pathlib import Path
from typing import Optional

from forrest.health.pi_power import read_temp_c, read_throttled


def parse_loadavg(text: str) -> list[float]:
    """'/proc/loadavg' -> [1 min, 5 min, 15 min]."""
    return [float(v) for v in text.split()[:3]]


def parse_meminfo(text: str) -> dict:
    """'/proc/meminfo' -> {'total_mb', 'available_mb', 'used_pct'}."""
    kb = {}
    for line in text.splitlines():
        key, _, rest = line.partition(":")
        if rest.strip():
            kb[key] = int(rest.split()[0])
    total, avail = kb["MemTotal"], kb["MemAvailable"]
    return {"total_mb": total // 1024, "available_mb": avail // 1024,
            "used_pct": round(100 * (total - avail) / total, 1)}


def parse_uptime(text: str) -> float:
    return float(text.split()[0])


def _read(path: str) -> Optional[str]:
    try:
        return Path(path).read_text()
    except OSError:
        return None


def read_status(disk_path: str = "/") -> dict:
    t = read_throttled()
    load = _read("/proc/loadavg")
    mem = _read("/proc/meminfo")
    up = _read("/proc/uptime")
    du = shutil.disk_usage(disk_path)
    return {
        "time": time.time(),
        "temp_c": read_temp_c(),
        "throttled": None if t is None else {"raw": hex(t.raw), "ok": t.ok,
                                             "problems": t.problems},
        "load": parse_loadavg(load) if load else None,
        "memory": parse_meminfo(mem) if mem else None,
        "uptime_s": parse_uptime(up) if up else None,
        "disk": {"total_gb": round(du.total / 1e9, 1), "free_gb": round(du.free / 1e9, 1),
                 "used_pct": round(100 * du.used / du.total, 1)},
    }
