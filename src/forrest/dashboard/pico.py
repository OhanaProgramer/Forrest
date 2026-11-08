"""Pico panel for the dashboard: the monitor's state file -> tiles + event list.

The dashboard never opens the Pico's port (the monitor holds it). It reads the
state file `forrest pico monitor` replaces every second
($XDG_RUNTIME_DIR/forrest/pico.json). Everything here is pure except
read_state(), so it is tested without a Pico or a monitor.

Levels (the dashboard's ok / warn / bad / na):
  link up                      ok
  Pico not plugged in          warn   expected on the bench, but worth seeing
  plugged in but not answering bad    the Pico is stuck or crashed
  monitor not running          na     no data (state file missing, or older than STALE_S)
Failsafe active is "ok" for now: with no controller, throttle cut is the correct
state. It becomes a warning once something is meant to be driving.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

from forrest.dashboard.status import level

STALE_S = 5.0          # the monitor writes every 1 s; 5 s without = not running


def read_state(path: Path) -> Optional[dict]:
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return None


def _hms(t: float) -> str:
    return time.strftime("%H:%M:%S", time.localtime(t))


def _ago(s: float) -> str:
    if s < 90:
        return f"{s:.0f} s"
    m = int(s // 60)
    return f"{m // 60} h {m % 60} min" if m >= 60 else f"{m} min"


def panel(snap: Optional[dict], now: float) -> dict:
    """-> {"tiles": [...], "events": [...], "monitor": "running" | "stopped"}.
    Tiles use the same shape as status.tiles(), in the "pico" group."""
    def tile(key, title, value, detail, lvl):
        return {"key": key, "title": title, "value": value, "detail": detail,
                "level": lvl, "group": "pico"}

    if snap is None or now - snap.get("updated", 0) > STALE_S:
        why = "no state file" if snap is None else f"last update {_ago(now - snap['updated'])} ago"
        return {"monitor": "stopped", "events": (snap or {}).get("events", []),
                "tiles": [tile("pico_link", "Pico link", "no data",
                               f"monitor not running ({why})\nsystemctl --user start forrest-pico", "na")]}

    link, s = snap["link"], snap.get("stat")
    since = f"since {_hms(snap['since'])}" if snap.get("since") else ""
    if link == "up":
        rtt = f"round trip {snap['rtt_ms']:.0f} ms" if snap.get("rtt_ms") is not None else ""
        lt = tile("pico_link", "Pico link", "up", " · ".join(x for x in (rtt, since) if x), "ok")
    elif link == "down":
        lt = tile("pico_link", "Pico link", "down",
                  f"not answering for {snap.get('last_answer_age_s', 0):.0f} s · {since}", "bad")
    else:
        lt = tile("pico_link", "Pico link", "not connected", f"no Pico on USB · {since}", "warn")
    tiles = [lt]

    if link == "up" and s:
        safe = snap.get("failsafe")
        age = _ago(s["age_ms"] / 1000)
        tiles.append(tile("pico_drive", "Drive output", "Failsafe" if safe else "Commanded",
                          f"throttle {s['throttle']} · steer {s['steer']} · ESC {s['esc_ns'] / 1e6:.3f} ms\n"
                          + (f"no command for {age}" if safe else f"last command {age} ago"), "ok"))
        tiles.append(tile("pico_loop", "Pico loop", f"{s['max_gap_ms']} ms",
                          "longest pause between passes", level("pico_gap_ms", s["max_gap_ms"])))
        trips = s.get("trips")
        last_trip = next((e for e in reversed(snap.get("events", [])) if e["kind"] == "FAILSAFE"), None)
        tiles.append(tile("pico_trips", "Failsafe trips", "–" if trips is None else str(trips),
                          "since Pico boot" + (f" · last {_hms(last_trip['t'])}" if last_trip else ""), "ok"))
    return {"monitor": "running", "tiles": tiles, "events": snap.get("events", [])}
