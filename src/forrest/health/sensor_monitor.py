"""Sensor monitor: listens to the sensor Pico W and publishes its readings.

Run as `forrest sensors monitor` (the `forrest-sensors` user service). It is the
one program that holds the sensor Pico's port; the dashboard reads its state
file and never opens the port. Same pattern as the LIDAR and drive Pico monitors.

The Pico pushes JSON lines (firmware/pico/sensors/main.py):
  READY  at boot              ENV  air, every 5 s (BME688)
  ACC    motion, every 1 s    EVT  FLIP / UPRIGHT / IMPACT, the moment it happens
  ENV/ACC with "err": that sensor is missing or stopped answering

State file (JSON, replaced atomically): $XDG_RUNTIME_DIR/forrest/sensors.json
  updated, link ("up" | "error" | "connecting"), since, error, fw
  env {t, rh, p, gas, gas_low, n, at} | null     env_err  text | null
  acc {x, y, z, tilt, face, peak, down, at} | null acc_err text | null
  events  the last few EVT (newest last), each with wall time "at"

Log (JSON lines, one file per day: data/sensors/sensors_YYYYMMDD.jsonl; "t" is
the wall time, so ENV's temperature is logged as temp_c): every ENV reading, an ACC sample every LOG_ACC_S, every EVT / READY / sensor error
(each new error once), and link changes.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Callable, Optional

from forrest.health.pico_monitor import DailyLog, write_state

RETRY_S = 2.0
PUBLISH_EVERY_S = 0.5
LOG_ACC_S = 10.0
KEEP_EVENTS = 10


def default_state_path() -> Path:
    run = os.environ.get("XDG_RUNTIME_DIR") or "/tmp"
    return Path(run) / "forrest" / "sensors.json"


def parse_line(raw) -> Optional[dict]:
    """One line from the Pico -> message dict, or None for noise (partial lines
    after a reconnect, MicroPython tracebacks, blank lines)."""
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", "replace")
    raw = raw.strip()
    if not raw.startswith("{"):
        return None
    try:
        msg = json.loads(raw)
    except ValueError:
        return None
    return msg if isinstance(msg, dict) and "k" in msg else None


class SensorState:
    """What the monitor knows. apply() takes one message and returns the log
    records it produces (pure; wall time is passed in)."""

    def __init__(self, wall: float):
        self.link, self.since, self.error = "connecting", wall, None
        self.fw = None
        self.env = self.acc = None
        self.env_err = self.acc_err = None
        self.events: list[dict] = []
        self._last_acc_log = -1e18

    def apply(self, msg: dict, wall: float) -> list[dict]:
        k = msg.get("k")
        out: list[dict] = []
        if k == "READY":
            self.fw = msg.get("fw")
            out.append({"t": wall, "kind": "READY", "fw": self.fw})
        elif k in ("ENV", "ACC"):
            err = msg.get("err")
            attr = "env" if k == "ENV" else "acc"
            if err is not None:
                if getattr(self, attr + "_err") != err:
                    out.append({"t": wall, "kind": k + "_ERR", "text": err})
                setattr(self, attr + "_err", err)
                setattr(self, attr, None)
            else:
                reading = {key: v for key, v in msg.items() if key not in ("k", "ms")}
                reading["at"] = wall
                if getattr(self, attr + "_err") is not None:
                    out.append({"t": wall, "kind": k + "_OK", "text": "sensor answering again"})
                setattr(self, attr + "_err", None)
                setattr(self, attr, reading)
                if k == "ENV":
                    # the Pico calls temperature "t"; in the log "t" is the time, so it's temp_c there
                    out.append({"t": wall, "kind": "ENV", "temp_c": reading.get("t"),
                                **{key: v for key, v in reading.items() if key not in ("at", "t")}})
                elif wall - self._last_acc_log >= LOG_ACC_S:
                    self._last_acc_log = wall
                    out.append({"t": wall, "kind": "ACC", **{key: v for key, v in reading.items() if key != "at"}})
        elif k == "EVT":
            ev = {"what": msg.get("what"), "v": msg.get("v"), "at": wall}
            self.events = (self.events + [ev])[-KEEP_EVENTS:]
            out.append({"t": wall, "kind": "EVT", "what": ev["what"], "v": ev["v"]})
        return out

    def set_link(self, link: str, wall: float, error: Optional[str] = None) -> list[dict]:
        if link == self.link and error == self.error:
            return []
        rec = {"t": wall, "kind": "LINK", "from": self.link, "to": link, "text": error or ""}
        self.link, self.error = link, error
        if rec["from"] != link:
            self.since = wall
        if link != "up":
            self.env = self.acc = None        # nothing current without the Pico
        return [rec]

    def snapshot(self, wall: float) -> dict:
        return {"updated": wall, "link": self.link, "since": self.since, "error": self.error,
                "fw": self.fw, "env": self.env, "env_err": self.env_err,
                "acc": self.acc, "acc_err": self.acc_err, "events": self.events}


def open_sensor_pico(baud: int = 115200):
    """The sensor Pico W's serial port, found by USB serial number."""
    import serial
    from serial.tools import list_ports

    from forrest.drivers.pico import board_port
    return serial.Serial(board_port(list_ports.comports(), "sensors"), baud, timeout=1.0)


def run(state_path: Path, log: Optional[DailyLog], open_port: Callable = open_sensor_pico,
        max_lines: Optional[int] = None, max_attempts: Optional[int] = None,
        wall=time.time, clock=time.monotonic, sleep=time.sleep,
        say: Callable[[str], None] = print) -> SensorState:
    """Listen until stopped. On any failure: record it, close, retry every RETRY_S.
    `max_lines` / `max_attempts` end the loop for tests."""
    st = SensorState(wall())
    lines = attempts = 0

    def emit(recs):
        for r in recs:
            if log is not None:
                log.write(r)
            if r["kind"] in ("LINK", "READY", "EVT", "ENV_ERR", "ACC_ERR", "ENV_OK", "ACC_OK"):
                say(f"{time.strftime('%H:%M:%S', time.localtime(r['t']))}  {r['kind']:8s} "
                    + " ".join(f"{k}={v}" for k, v in r.items() if k not in ("t", "kind")))

    while max_attempts is None or attempts < max_attempts:
        attempts += 1
        port = None
        try:
            port = open_port()
            last_pub = -1e9
            while max_lines is None or lines < max_lines:
                raw = port.readline()
                now = clock()
                if raw:
                    lines += 1
                    msg = parse_line(raw)
                    if msg is not None:
                        emit(st.set_link("up", wall()))
                        emit(st.apply(msg, wall()))
                if now - last_pub >= PUBLISH_EVERY_S:
                    write_state(state_path, st.snapshot(wall()))
                    last_pub = now
            write_state(state_path, st.snapshot(wall()))
            return st
        except (OSError, RuntimeError) as e:       # unplugged / not on USB (PicoError)
            emit(st.set_link("error", wall(), str(e)))
            write_state(state_path, st.snapshot(wall()))
        finally:
            if port is not None:
                try:
                    port.close()
                except OSError:
                    pass
        sleep(RETRY_S)
    return st
