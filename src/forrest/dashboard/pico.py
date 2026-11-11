"""Pico panel for the dashboard: the Picos' state -> tiles + event list.

Two sources, and the dashboard never opens a Pico's port:
  * the drive Pico: the state file `forrest pico monitor` replaces every second
    ($XDG_RUNTIME_DIR/forrest/pico.json); the monitor holds that port.
  * every other board in drivers.pico.BOARDS (the sensor Pico W, ...): USB
    presence only, from the list of serial ports the OS already knows. That
    reads /sys, opens nothing, so it can't disturb a board or steal its port.
    A board gets link/status tiles once it has firmware and a monitor.
  * any MicroPython board that isn't in BOARDS shows as a caution, so a new or
    reflashed board (whose serial changed) is noticed, not silently ignored.
Everything here is pure except read_state() and usb_ports(), so it is tested
without a Pico or a monitor.

Levels (the dashboard's ok / warn / bad / na):
  link up                      ok
  Pico not plugged in          warn   expected on the bench, but worth seeing
  other board on USB           ok     (presence only)
  unknown MicroPython board    warn    add its serial to BOARDS
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
from forrest.drivers.pico import BOARDS, micropython_ports, role_of

STALE_S = 5.0          # the monitor writes every 1 s; 5 s without = not running


TITLES = {"drive": "Drive Pico", "sensors": "Sensor Pico"}


def usb_ports() -> list:
    """The OS's serial ports (pyserial). Lists only; opens nothing."""
    try:
        from serial.tools import list_ports
        return list(list_ports.comports())
    except Exception:          # pyserial missing or /sys unreadable: just no board tiles
        return []


def board_tiles(ports) -> list[dict]:
    """USB-presence tiles for every board in BOARDS except the drive (the
    monitor covers that), plus one caution tile for unknown MicroPython boards."""
    def tile(key, title, value, detail, lvl):
        return {"key": key, "title": title, "value": value, "detail": detail,
                "level": lvl, "group": "pico", "source": "USB serial number (/sys, port not opened)"}

    mp = micropython_ports(ports)
    by_serial = {(getattr(p, "serial_number", None) or "").lower(): p for p in mp}
    out = []
    for role, serial in BOARDS.items():
        if role == "drive":
            continue
        title = TITLES.get(role, f"{role.capitalize()} Pico")
        p = by_serial.get(serial.lower())
        if p is None:
            out.append(tile(f"pico_{role}", title, "not connected",
                            f"serial {serial} not on USB", "warn"))
        else:
            out.append(tile(f"pico_{role}", title, "on USB",
                            f"{p.device} · serial {serial}\npresence only, not monitored yet", "ok"))
    unknown = [p for p in mp if role_of(getattr(p, "serial_number", None)) is None]
    if unknown:
        out.append(tile("pico_unknown", "Unknown Pico", str(len(unknown)),
                        " · ".join(f"{p.device} serial {getattr(p, 'serial_number', None)}" for p in unknown)
                        + "\nnot in BOARDS: the Pi won't use it", "warn"))
    return out


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


def panel(snap: Optional[dict], now: float, ports=()) -> dict:
    """-> {"tiles": [...], "events": [...], "monitor": "running" | "stopped"}.
    Tiles use the same shape as status.tiles(), in the "pico" group: the drive
    Pico's tiles (from the monitor's state `snap`), then the other boards'
    USB-presence tiles (from `ports`)."""
    out = _drive_panel(snap, now)
    out["tiles"] += board_tiles(ports)
    return out


def _drive_panel(snap: Optional[dict], now: float) -> dict:
    def tile(key, title, value, detail, lvl):
        return {"key": key, "title": title, "value": value, "detail": detail,
                "level": lvl, "group": "pico", "source": "forrest-pico monitor (STAT reply to \"?\")"}

    if snap is None or now - snap.get("updated", 0) > STALE_S:
        why = "no state file" if snap is None else f"last update {_ago(now - snap['updated'])} ago"
        return {"monitor": "stopped", "events": (snap or {}).get("events", []),
                "tiles": [tile("pico_link", "Drive Pico", "no data",
                               f"monitor not running ({why})\nsystemctl --user start forrest-pico", "na")]}

    link, s = snap["link"], snap.get("stat")
    since = f"since {_hms(snap['since'])}" if snap.get("since") else ""
    if link == "up":
        rtt = f"round trip {snap['rtt_ms']:.0f} ms" if snap.get("rtt_ms") is not None else ""
        lt = tile("pico_link", "Drive Pico", "up", " · ".join(x for x in (rtt, since) if x), "ok")
    elif link == "down":
        lt = tile("pico_link", "Drive Pico", "down",
                  f"not answering for {snap.get('last_answer_age_s', 0):.0f} s · {since}", "bad")
    else:
        lt = tile("pico_link", "Drive Pico", "not connected",
                  f"serial {BOARDS['drive']} not on USB · {since}", "warn")
    tiles = [lt]

    if link == "up" and s:
        safe = snap.get("failsafe")
        age = _ago(s["age_ms"] / 1000)
        tiles.append(tile("pico_drive", "Drive output", "Failsafe" if safe else "Commanded",
                          f"throttle {s['throttle']} · steer {s['steer']} · ESC {s['esc_ns'] / 1e6:.3f} ms\n"
                          + (f"no command for {age}" if safe else f"last command {age} ago"), "ok"))
        tiles.append(tile("pico_loop", "Drive loop", f"{s['max_gap_ms']} ms",
                          "longest pause between passes", level("pico_gap_ms", s["max_gap_ms"])))
        trips = s.get("trips")
        last_trip = next((e for e in reversed(snap.get("events", [])) if e["kind"] == "FAILSAFE"), None)
        tiles.append(tile("pico_trips", "Failsafe trips", "–" if trips is None else str(trips),
                          "since Pico boot" + (f" · last {_hms(last_trip['t'])}" if last_trip else ""), "ok"))
    return {"monitor": "running", "tiles": tiles, "events": snap.get("events", [])}
