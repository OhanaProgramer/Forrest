"""LIDAR monitor: runs the RPLIDAR C1 and publishes the latest scan.

Run as `forrest lidar monitor` (the `forrest-lidar` user service). It is the one
program that holds the LIDAR's port; the dashboard reads its state file and
never opens the port. Same pattern as forrest.health.pico_monitor.

What it decides: is the LIDAR scanning, and what does the latest rotation look
like. To keep the file small (the dashboard fetches it several times a second),
a scan (~410 points) is reduced to the nearest distance per BIN_DEG-degree bin:
180 numbers, ~1.5 KB. The radar only needs "where is the nearest thing in each
direction"; full scans are for `forrest lidar record`.

State file (JSON, replaced atomically): $XDG_RUNTIME_DIR/forrest/lidar.json
  updated   wall time of this write
  link      "up" (scanning) | "connecting" (opening the port / motor spin-up)
            | "error" (can't open / stopped answering)
  since     wall time of the last link change
  down_since wall time the LIDAR stopped scanning (the outage start, kept
            through error -> connecting -> error retries); null while up
  error     text, when link is "error"
  device    {model, firmware, hardware, serial}, once read
  rate_hz   rotations per second (smoothed)
  points    points in the latest rotation
  bin_deg   width of each bin, degrees
  bins      nearest distance (m) per bin, clockwise from the LIDAR's 0 deg
            (its forward mark), null where nothing was seen
  sectors   nearest distance per named 45-degree sector (as `forrest lidar check`)

Log (JSON lines, one file per day: data/lidar/lidar_YYYYMMDD.jsonl): every
link change (LINK, with how long the LIDAR was down when it comes back) and a
SAMPLE every LOG_SAMPLE_S (rate, points, sectors). Not the scans themselves: a
scan every 0.1 s is too much to log; `forrest lidar record` is for that.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Callable, Optional

from forrest.health.pico_monitor import DailyLog, write_state
from forrest.sensing.scan import Scan, sector_nearest

BIN_DEG = 2
PUBLISH_EVERY_S = 0.2        # 5 writes/s; the LIDAR turns at ~10 Hz
RETRY_S = 2.0
LOG_SAMPLE_S = 10.0


def default_state_path() -> Path:
    run = os.environ.get("XDG_RUNTIME_DIR") or "/tmp"
    return Path(run) / "forrest" / "lidar.json"


# ---------------------------------------------------------------------------
# Pure parts (tested)
# ---------------------------------------------------------------------------

def bin_scan(scan: Scan, bin_deg: int = BIN_DEG) -> list[Optional[float]]:
    """Nearest distance (m, rounded to 1 cm) per bin; None where no point fell."""
    n = 360 // bin_deg
    out: list[Optional[float]] = [None] * n
    for p in scan.points:
        if p.distance_m <= 0:
            continue
        i = int((p.angle_deg % 360) // bin_deg) % n
        if out[i] is None or p.distance_m < out[i]:
            out[i] = p.distance_m
    return [None if d is None else round(d, 2) for d in out]


class RateMeter:
    """Rotations per second, smoothed (as `forrest lidar check` shows it)."""

    def __init__(self):
        self.rate = 0.0
        self._last: Optional[float] = None

    def tick(self, now: float) -> float:
        if self._last is not None:
            inst = 1.0 / max(now - self._last, 1e-3)
            self.rate = inst if self.rate == 0 else 0.8 * self.rate + 0.2 * inst
        self._last = now
        return self.rate


def snapshot(link: str, since: float, wall: float, *, device=None, error=None,
             scan: Optional[Scan] = None, rate_hz: float = 0.0,
             down_since: Optional[float] = None) -> dict:
    snap = {"updated": wall, "link": link, "since": since, "down_since": down_since,
            "error": error,
            "device": device, "rate_hz": round(rate_hz, 1), "bin_deg": BIN_DEG,
            "points": 0, "bins": None, "sectors": None}
    if scan is not None:
        snap.update(points=len(scan.points), bins=bin_scan(scan),
                    sectors={k: (None if v is None else round(v, 2))
                             for k, v in sector_nearest(scan).items()})
    return snap


# ---------------------------------------------------------------------------
# The loop
# ---------------------------------------------------------------------------

def run(state_path: Path, open_lidar: Callable, max_scans: Optional[int] = None,
        max_attempts: Optional[int] = None, clock=time.monotonic, wall=time.time,
        sleep=time.sleep, say: Callable[[str], None] = print,
        log: Optional[DailyLog] = None) -> None:
    """Scan until stopped. On any failure: write the error, close, retry every
    RETRY_S. `max_scans` / `max_attempts` end the loop for tests. `log`, when
    given, gets every link change and a SAMPLE every LOG_SAMPLE_S."""
    link, since, last_error = None, wall(), None
    down_since: Optional[float] = wall()     # not scanning yet = down from the start
    scans = attempts = 0

    logged = None                            # (state, text) last said / logged

    def change(new: str, why: str):
        """Move the link state. Say and log only what's news: going up, or a new
        error. A retry loop (connecting -> same error, every RETRY_S while
        unplugged) stays quiet after its first error."""
        nonlocal link, since, down_since, logged
        if new == link:
            return
        now = wall()
        rec = {"t": now, "kind": "LINK", "from": (logged or ("start",))[0], "to": new, "text": why}
        if new == "up":
            rec["down_s"] = round(now - down_since, 1) if down_since is not None else None
            down_since = None
        elif down_since is None:
            down_since = now                  # the outage starts here
        link, since = new, now
        if new == "connecting" or logged == (new, why):
            return
        logged = (new, why)
        extra = f" (down {rec['down_s']} s)" if rec.get("down_s") is not None else ""
        say(f"{time.strftime('%H:%M:%S')}  LINK     {rec['from']} -> {new}: {why}{extra}")
        if log is not None:
            log.write(rec)

    while max_attempts is None or attempts < max_attempts:
        attempts += 1
        lidar = None
        # Say "connecting" before the slow part (open + info + motor spin-up, ~2.5 s,
        # up to SPINUP_TIMEOUT_S), so the dashboard doesn't read the quiet file as
        # "monitor stopped".
        change("connecting", f"attempt {attempts}")
        write_state(state_path, snapshot("connecting", since, wall(), error=last_error,
                                         down_since=down_since))
        try:
            lidar = open_lidar()
            # A killed monitor (systemctl restart) never sent STOP, so the LIDAR may
            # still be streaming a scan; stop it first or GET_INFO reads scan bytes.
            lidar.stop()
            info, health = lidar.info(), lidar.health()
            device = {"model": info.model, "firmware": info.firmware,
                      "hardware": info.hardware, "serial": info.serial}
            if health.status != "good":
                raise RuntimeError(f"LIDAR health {health.status} (code {health.error_code})")
            rate, last_pub, last_log = RateMeter(), -1e9, -1e9
            for scan in lidar.iter_scans():
                scans += 1
                now = clock()
                rate.tick(now)
                change("up", f"scanning, model {info.model} fw {info.firmware}")
                if now - last_pub >= PUBLISH_EVERY_S:
                    snap = snapshot("up", since, wall(), device=device,
                                    scan=scan, rate_hz=rate.rate)
                    write_state(state_path, snap)
                    last_pub = now
                    if log is not None and now - last_log >= LOG_SAMPLE_S:
                        log.write({"t": snap["updated"], "kind": "SAMPLE", "rate_hz": snap["rate_hz"],
                                   "points": snap["points"], "sectors": snap["sectors"]})
                        last_log = now
                if max_scans is not None and scans >= max_scans:
                    return
        except (OSError, RuntimeError) as e:     # SerialException is an OSError; LidarError a RuntimeError
            last_error = str(e)
            change("error", last_error)
            write_state(state_path, snapshot("error", since, wall(), error=last_error,
                                             down_since=down_since))
        finally:
            if lidar is not None:
                try:
                    lidar.close()                # sends STOP: the motor winds down
                except (OSError, RuntimeError):
                    pass
        sleep(RETRY_S)
