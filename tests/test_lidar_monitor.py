"""LIDAR monitor (forrest.health.lidar_monitor) and the dashboard radar panel, no hardware."""
import json

from forrest.dashboard import lidar as dl
from forrest.drivers.lidar_c1 import DeviceInfo, Health
from forrest.health import lidar_monitor as lm
from forrest.sensing.scan import Scan, ScanPoint


def test_bin_scan_keeps_the_nearest_per_bin_and_wraps():
    scan = Scan(0.0, [ScanPoint(0.5, 2.0), ScanPoint(1.9, 1.234), ScanPoint(359.9, 3.0),
                      ScanPoint(360.0, 0.9), ScanPoint(90.0, 0.0)])          # 0.0 m = no return
    b = lm.bin_scan(scan)
    assert len(b) == 180
    assert b[0] == 0.9                         # 0.5, 1.9 and 360.0 all land in bin 0
    assert b[179] == 3.0
    assert b[45] is None                       # the zero-distance point is dropped


def test_rate_meter():
    r = lm.RateMeter()
    assert r.tick(0.0) == 0.0
    assert abs(r.tick(0.1) - 10.0) < 1e-6      # first interval taken as is
    assert 9.0 < r.tick(0.2) < 11.0


class FakeLidar:
    def __init__(self, scans, health="good", fail_after=None):
        self.scans, self._health, self.fail_after, self.closed = scans, health, fail_after, False

    def info(self):
        return DeviceInfo(65, "1.02", 18, "B120")

    def health(self):
        return Health(self._health, 0)

    def iter_scans(self):
        for i, s in enumerate(self.scans):
            if self.fail_after is not None and i >= self.fail_after:
                raise OSError("device disconnected")
            yield s

    def close(self):
        self.closed = True


def _scan(d=1.0):
    return Scan(0.0, [ScanPoint(a, d) for a in range(0, 360, 1)])


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        self.t += 0.1                          # every call: one LIDAR rotation later
        return self.t


def test_run_publishes_scans(tmp_path):
    state, lidar = tmp_path / "lidar.json", FakeLidar([_scan(1.0)] * 5)
    lm.run(state, lambda: lidar, max_scans=5, clock=Clock(), wall=lambda: 100.0,
           sleep=lambda s: None, say=lambda m: None)
    snap = json.loads(state.read_text())
    assert snap["link"] == "up" and snap["points"] == 360 and snap["bins"][0] == 1.0
    assert snap["device"]["model"] == 65 and snap["sectors"]["front"] == 1.0
    assert lidar.closed                        # STOP sent on the way out


def test_run_reports_errors_and_retries(tmp_path):
    state = tmp_path / "lidar.json"
    opened = []

    def open_lidar():
        opened.append(1)
        if len(opened) == 1:
            raise OSError("could not open port /dev/ttyUSB0")
        return FakeLidar([_scan()] * 3, fail_after=2)

    lm.run(state, open_lidar, max_attempts=2, clock=Clock(), wall=lambda: 100.0,
           sleep=lambda s: None, say=lambda m: None)
    snap = json.loads(state.read_text())
    assert len(opened) == 2
    assert snap["link"] == "error" and "disconnected" in snap["error"] and snap["bins"] is None


def test_bad_health_is_an_error(tmp_path):
    state = tmp_path / "lidar.json"
    lm.run(state, lambda: FakeLidar([_scan()], health="error"), max_attempts=1,
           sleep=lambda s: None, say=lambda m: None)
    assert "health error" in json.loads(state.read_text())["error"]


# -- dashboard panel --------------------------------------------------------------

NOW = 1000.0


def _snap(**over):
    s = lm.snapshot("up", NOW - 30, NOW - 0.1, device={"model": 65}, scan=_scan(1.5), rate_hz=9.94)
    s.update(over)
    return s


def test_panel_running():
    p = dl.panel(_snap(), NOW)
    assert p["running"] and p["state"] == "running" and p["error"] is None
    assert len(p["bins"]) == 180 and p["rate_hz"] == 9.9 and p["age_s"] == 0.1


def test_panel_error_and_stopped():
    e = dl.panel(_snap(link="error", error="timed out", bins=None), NOW)
    assert not e["running"] and e["state"] == "error" and "timed out" in e["error"]
    stale = dl.panel(_snap(updated=NOW - 10), NOW)
    assert stale["state"] == "stopped" and "10 s ago" in stale["error"] and stale["bins"] is None
    missing = dl.panel(None, NOW)
    assert missing["state"] == "stopped" and "forrest-lidar" in missing["error"]
