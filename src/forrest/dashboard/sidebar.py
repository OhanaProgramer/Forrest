"""Sidebar for the dashboard: the always-on numbers (environment, position, robot).

Pure: takes what the sensors have reported (None = no sensor yet) and returns
sections of rows for the page. Each row: label, value, detail, level
(ok / warn / bad / na), the same levels as the tiles.

Sensors as of 2026-11-23: BME688 (air) + LIS3DH (motion) on the sensor Pico W,
read by `forrest-sensors` (forrest.dashboard.sensors turns its state into env /
motion here). Planned:
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
            battery_v: Optional[float] = None, pico: Optional[dict] = None,
            motion: Optional[dict] = None, env_why: str = "no sensor yet",
            motion_why: str = "no sensor yet") -> list[dict]:
    """-> [{"key", "title", "rows": [...]}, ...] in display order.

    env:    {"temp_c", "humidity_pct", "pressure_hpa", "gas_ohm", "gas_low"}  (BME688)
    motion: {"face", "tilt_deg", "upside_down", "peak_g", "last_event"}       (LIS3DH)
    env_why / motion_why: why there's no reading (shown instead of numbers)
    gps:  {"lat", "lon", "sats", "fix", "speed_mps", "heading_deg"}   (later)
    pico: the dashboard Pico panel (forrest.dashboard.pico.panel output)
    """
    out = []

    if env is None:
        rows = [_none("Air temp", env_why), _none("Humidity", env_why),
                _none("Pressure", env_why), _none("Gas", env_why)]
    else:
        rows = [_row("Air temp", f"{env['temp_c']:.1f} °C"),
                _row("Humidity", f"{env['humidity_pct']:.0f} %"),
                _row("Pressure", f"{env['pressure_hpa']:.0f} hPa")]
        gas = env.get("gas_ohm")
        if gas is None:
            rows.append(_none("Gas", "heater warming up"))
        elif env.get("gas_low"):
            rows.append(_row("Gas", f"≤ {gas / 1000:.1f} kΩ", "below range: new sensor, burn-in", "warn"))
        else:
            rows.append(_row("Gas", f"{gas / 1000:.1f} kΩ",
                             "raw resistance; higher = cleaner air (meaningful after ~24 h burn-in)"))
    out.append({"key": "env", "title": "Environment", "rows": rows})

    if motion is None:
        rows = [_none("Orientation", motion_why), _none("Tilt", motion_why), _none("Last event", motion_why)]
    else:
        down = motion.get("upside_down")
        face = motion.get("face") or "?"
        label = {"up": "level, face up", "down": "upside down", "moving": "moving"}.get(face, f"on its side ({face})")
        rows = [_row("Orientation", "UPSIDE DOWN" if down else label, "", "bad" if down else "ok"),
                _row("Tilt", f"{motion.get('tilt_deg', 0):.0f}°", f"peak {motion.get('peak_g', 0):.2f} g in the last second")]
        ev = motion.get("last_event")
        if ev is None:
            rows.append(_row("Last event", "none", "no flip or impact in the last 10 min"))
        else:
            what = {"IMPACT": f"impact {ev['v']:.1f} g", "FLIP": "flipped over", "UPRIGHT": "back upright"}.get(
                ev["what"], ev["what"])
            ago = ev["ago_s"]
            rows.append(_row("Last event", what, f"{ago:.0f} s ago" if ago < 90 else f"{ago / 60:.0f} min ago",
                             "warn" if ev["what"] in ("IMPACT", "FLIP") else "ok"))
    out.append({"key": "motion", "title": "Motion", "rows": rows})

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
