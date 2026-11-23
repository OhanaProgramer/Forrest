"""Sensor Pico W path without hardware: LIS3DH maths + motion logic (firmware),
the Pi's sensor monitor, the dashboard sensor panel and sidebar rows."""
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "firmware/pico/sensors"))
import lis3dh  # noqa: E402

from forrest.dashboard import sensors as sp  # noqa: E402
from forrest.dashboard.sidebar import sidebar  # noqa: E402
from forrest.health import sensor_monitor as sm  # noqa: E402
from forrest.health.pico_monitor import DailyLog  # noqa: E402


# -- LIS3DH (firmware) ----------------------------------------------------------

def _raw(xg, yg, zg):
    """g -> the 6 register bytes (12-bit left-justified, 4 mg/digit at +-8 g)."""
    return struct.pack("<hhh", *(int(round(v * 1000 / 4)) << 4 for v in (xg, yg, zg)))


def test_raw_to_g_and_angles():
    x, y, z = lis3dh.raw_to_g(_raw(0.0, 0.0, 1.0))
    assert (x, y, z) == (0.0, 0.0, 1.0)
    assert lis3dh.raw_to_g(_raw(0, -2.0, 0))[1] == -2.0          # negative values survive the shift
    assert round(lis3dh.tilt_deg(0, 0, 1)) == 0 and round(lis3dh.tilt_deg(0, 0, -1)) == 180
    assert round(lis3dh.tilt_deg(0, 1, 0)) == 90


def test_face():
    assert lis3dh.face(0.03, 0.17, 0.99) == "up"
    assert lis3dh.face(0.05, 0.61, -0.94) == "down"
    assert lis3dh.face(0.09, 0.85, 0.48) == "edge+y" and lis3dh.face(-0.95, 0.1, 0.1) == "side-x"
    assert lis3dh.face(0.5, 0.5, 0.5) == "moving"


def test_flip_needs_to_be_held():
    m = lis3dh.Motion()
    assert m.update(0, 0, -1, 0) == [] and m.update(0, 0, -1, 400) == []
    assert m.update(0, 0, 1, 450) == []                           # a flick, not a flip
    assert m.update(0, 0, -1, 500) == [] and m.update(0, 0, -1, 1000) == [("FLIP", -1)]
    assert m.upside_down
    assert m.update(0, 0, 1, 1100) == [] and m.update(0, 0, 1, 1600) == [("UPRIGHT", 1)]


def test_impact_once_per_gap_and_peak():
    m = lis3dh.Motion()
    assert m.update(0, 0, 3.0, 0) == [("IMPACT", 3.0)]
    assert m.update(0, 0, 3.2, 100) == []                         # same hit, inside the gap
    assert m.update(2.0, 0, 2.0, 700) == [("IMPACT", 2.83)]
    assert m.take_peak() == 3.2 and m.take_peak() == 0.0


# -- monitor (Pi) --------------------------------------------------------------

ENV = b'{"k":"ENV","t":22.83,"rh":40.69,"p":831.32,"gas":8091,"gas_low":false,"n":2,"ms":11143}\n'
ACC = b'{"k":"ACC","x":0.012,"y":-0.004,"z":0.984,"tilt":1,"face":"up","peak":1.0,"down":false,"ms":20742}\n'


def test_parse_line_skips_noise():
    assert sm.parse_line(ENV)["t"] == 22.83
    for junk in (b"", b"MPY: soft reboot\n", b'{"t": 1', b'Traceback (most recent call last):', b"[1,2]", b'{"x":1}'):
        assert sm.parse_line(junk) is None


def test_state_logs_env_each_time_acc_every_10s_errors_once():
    st = sm.SensorState(0.0)
    assert [r["kind"] for r in st.apply(sm.parse_line(ENV), 1.0)] == ["ENV"]
    assert st.env["gas"] == 8091 and st.env["at"] == 1.0
    rec = st.apply(sm.parse_line(ENV), 2.0)[0]
    assert rec["t"] == 2.0 and rec["temp_c"] == 22.83     # the Pico's "t" (temperature) must not overwrite the time
    assert [r["kind"] for r in st.apply(sm.parse_line(ACC), 1.0)] == ["ACC"]
    assert st.apply(sm.parse_line(ACC), 5.0) == []                 # ACC logged every LOG_ACC_S
    assert [r["kind"] for r in st.apply(sm.parse_line(ACC), 11.5)] == ["ACC"]
    err = {"k": "ENV", "err": "read failed: [Errno 5] EIO"}
    assert [r["kind"] for r in st.apply(err, 12.0)] == ["ENV_ERR"]
    assert st.apply(err, 17.0) == [] and st.env is None             # same error: logged once
    assert [r["kind"] for r in st.apply(sm.parse_line(ENV), 20.0)] == ["ENV_OK", "ENV"]
    recs = st.apply({"k": "EVT", "what": "IMPACT", "v": 3.1}, 21.0)
    assert recs[0]["what"] == "IMPACT" and st.events[-1]["at"] == 21.0


class FakePort:
    def __init__(self, lines):
        self.lines, self.closed = list(lines), False

    def readline(self):
        if not self.lines:
            raise OSError("device disconnected")
        return self.lines.pop(0)

    def close(self):
        self.closed = True


def test_run_writes_state_and_log_and_survives_unplug(tmp_path):
    state = tmp_path / "sensors.json"
    log = DailyLog(tmp_path / "log", prefix="sensors")
    opened = []

    def open_port():
        opened.append(1)
        if len(opened) == 1:
            return FakePort([b'{"k":"READY","fw":"sensors 1"}\n', b"garbage\n", ENV, ACC])
        raise RuntimeError("sensors Pico (serial e661) not on USB")

    clock = iter(range(1000))
    st = sm.run(state, log, open_port, max_attempts=2, wall=lambda: 100.0,
                clock=lambda: next(clock), sleep=lambda s: None, say=lambda m: None)
    snap = json.loads(state.read_text())
    assert snap["link"] == "error" and "not on USB" in snap["error"] and snap["env"] is None
    assert st.fw == "sensors 1"
    kinds = [json.loads(l)["kind"] for f in (tmp_path / "log").iterdir() for l in f.read_text().splitlines()]
    # up, readings, the unplug, then "not on USB" (a new error text, so logged)
    assert kinds == ["LINK", "READY", "ENV", "ACC", "LINK", "LINK"]


# -- dashboard ---------------------------------------------------------------

NOW = 1000.0


def _snap(**over):
    s = {"updated": NOW - 0.2, "link": "up", "since": NOW - 60, "error": None, "fw": "sensors 1",
         "env": {"t": 22.8, "rh": 40.7, "p": 831.3, "gas": 16500, "gas_low": False, "n": 9, "at": NOW - 2},
         "env_err": None,
         "acc": {"x": 0.0, "y": 0.0, "z": 1.0, "tilt": 1, "face": "up", "peak": 1.01, "down": False, "at": NOW - 0.5},
         "acc_err": None, "events": []}
    s.update(over)
    return s


def test_panel_up():
    p = sp.panel(_snap(), NOW)
    assert p["env"]["temp_c"] == 22.8 and p["env"]["gas_ohm"] == 16500
    assert p["motion"]["face"] == "up" and p["motion"]["last_event"] is None
    assert p["tile"]["value"] == "up" and p["tile"]["level"] == "ok"


def test_panel_stale_missing_and_errors():
    assert sp.panel(None, NOW)["tile"]["value"] == "no monitor"
    assert sp.panel(_snap(updated=NOW - 30), NOW)["monitor"] == "stopped"
    off = sp.panel(_snap(link="error", error="not on USB"), NOW)
    assert off["env"] is None and off["tile"]["value"] == "not connected"
    old = sp.panel(_snap(env={**_snap()["env"], "at": NOW - 40}), NOW)
    assert old["env"] is None and "40 s ago" in old["env_why"] and old["tile"]["value"] == "partial"
    bad = sp.panel(_snap(acc=None, acc_err="no sensor: [Errno 19] ENODEV"), NOW)
    assert bad["motion"] is None and "ENODEV" in bad["motion_why"]


def test_sidebar_rows_from_panel():
    p = sp.panel(_snap(events=[{"what": "IMPACT", "v": 3.1, "at": NOW - 30}]), NOW)
    s = sidebar(env=p["env"], motion=p["motion"])
    env = {r["label"]: r for r in next(x for x in s if x["key"] == "env")["rows"]}
    mot = {r["label"]: r for r in next(x for x in s if x["key"] == "motion")["rows"]}
    assert env["Air temp"]["value"] == "22.8 °C" and env["Gas"]["value"] == "16.5 kΩ"
    assert mot["Orientation"]["value"] == "level, face up"
    assert mot["Last event"]["value"] == "impact 3.1 g" and mot["Last event"]["level"] == "warn"
    flipped = sp.panel(_snap(acc={**_snap()["acc"], "z": -1.0, "face": "down", "down": True}), NOW)
    mot = {r["label"]: r for r in next(x for x in sidebar(motion=flipped["motion"]) if x["key"] == "motion")["rows"]}
    assert mot["Orientation"]["value"] == "UPSIDE DOWN" and mot["Orientation"]["level"] == "bad"
    low = sidebar(env={**p["env"], "gas_ohm": 5684, "gas_low": True})
    assert next(x for x in low if x["key"] == "env")["rows"][3]["value"] == "≤ 5.7 kΩ"
