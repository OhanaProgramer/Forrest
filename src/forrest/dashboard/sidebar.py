"""Sidebar for the dashboard: the always-on numbers (environment, position, robot).

Pure: takes what the sensors have reported (None = no sensor yet) and returns
sections of rows for the page. Each row: label, value, detail, level
(ok / warn / bad / na), the same levels as the tiles.

Sensors as of 2026-11-08: none fitted. Planned (shopping list in HANDOFF.md):
  * air temperature / humidity / pressure: BME280-class board on the Pi's I2C
  * position: USB GPS (u-blox M8/M9) on the Pi
  * battery voltage: divider into a Pico ADC pin, reported in the Pico's STAT
When a driver exists, pass its reading in and the row fills itself in.
"""

from __future__ import annotations

from typing import Optional


def _row(label, value, detail="", lvl="ok"):
    return {"label": label, "value": value, "detail": detail, "level": lvl}


def _none(label, why):
    return _row(label, "–", why, "na")


def sidebar(env: Optional[dict] = None, gps: Optional[dict] = None,
            battery_v: Optional[float] = None, pico: Optional[dict] = None) -> list[dict]:
    """-> [{"key", "title", "rows": [...]}, ...] in display order.

    env:  {"temp_c", "humidity_pct", "pressure_hpa"}   (from the BME280 driver, later)
    gps:  {"lat", "lon", "sats", "fix", "speed_mps", "heading_deg"}   (later)
    pico: the dashboard Pico panel (forrest.dashboard.pico.panel output)
    """
    out = []

    if env is None:
        rows = [_none("Air temp", "no sensor yet"), _none("Humidity", "no sensor yet"),
                _none("Pressure", "no sensor yet")]
    else:
        rows = [_row("Air temp", f"{env['temp_c']:.1f} °C"),
                _row("Humidity", f"{env['humidity_pct']:.0f} %"),
                _row("Pressure", f"{env['pressure_hpa']:.0f} hPa")]
    out.append({"key": "env", "title": "Environment", "rows": rows})

    if gps is None:
        rows = [_none("Position", "no GPS yet"), _none("Satellites", "no GPS yet"),
                _none("Speed", "no GPS yet")]
    else:
        fixed = bool(gps.get("fix"))
        rows = [_row("Position", f"{gps['lat']:.5f}, {gps['lon']:.5f}" if fixed else "no fix",
                     "", "ok" if fixed else "warn"),
                _row("Satellites", str(gps.get("sats", 0)), "fix" if fixed else "searching",
                     "ok" if fixed else "warn"),
                _row("Speed", f"{gps.get('speed_mps', 0):.1f} m/s",
                     f"heading {gps['heading_deg']:.0f}°" if gps.get("heading_deg") is not None else "")]
    out.append({"key": "gps", "title": "Position", "rows": rows})

    rows = [_none("Battery", "no sensor yet (Pico ADC, planned)") if battery_v is None
            else _row("Battery", f"{battery_v:.2f} V")]
    tiles = {t["key"]: t for t in (pico or {}).get("tiles", [])}
    link = tiles.get("pico_link")
    drive = tiles.get("pico_drive")
    if link is None or link["level"] == "na":
        rows.append(_none("Drive Pico", "monitor not running"))
    else:
        rows.append(_row("Drive Pico", link["value"], "", link["level"]))
    if drive is not None:
        safe = drive["value"] == "Failsafe"
        rows.append(_row("Drive", "failsafe" if safe else "commanded",
                         "throttle cut, nothing driving" if safe else "a controller is driving", "ok"))
    else:
        rows.append(_none("Drive", "unknown without the drive Pico"))
    sensors = tiles.get("pico_sensors")
    if sensors is not None:
        rows.append(_row("Sensor Pico", sensors["value"], "", sensors["level"]))
    out.append({"key": "robot", "title": "Robot", "rows": rows})
    return out
