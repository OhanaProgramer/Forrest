"""Pico monitor: watches the Pico 2 over USB and publishes its state.

Run as `forrest pico monitor` (the `forrest-pico` user service). It is the one
program that holds the Pico's port. It is read-only: it polls "?" and never
sends a drive command, so it can't keep the drive alive (the Pico stays in
failsafe unless a controller is feeding its heartbeat).

What it decides: whether the link is up. A poll answered = up. No answer for
DOWN_AFTER_S seconds, or the port vanished = down. With no device it
retries every RETRY_S seconds and picks the Pico up again when it's plugged in.

Outputs:
  * state file (JSON, replaced atomically each poll): what the dashboard reads.
    Default $XDG_RUNTIME_DIR/forrest/pico.json (RAM, gone at reboot: it's "now").
  * log (JSON lines, one file per day in data/pico/): every event and link
    change, plus one status sample every LOG_SAMPLE_S seconds. At 1 poll/s,
    logging every poll would be ~13 MB/day; this is ~1.3 MB/day.
"""

from __future__ import annotations

import json
import os
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

DOWN_AFTER_S = 3.0
RETRY_S = 2.0
LOG_SAMPLE_S = 10.0
FAILSAFE_MS = 500        # matches firmware main.py FAILSAFE_MS
RECENT_EVENTS = 20       # kept in the state file for the dashboard's trip log


def default_state_path() -> Path:
    run = os.environ.get("XDG_RUNTIME_DIR") or "/tmp"
    return Path(run) / "forrest" / "pico.json"


# ---------------------------------------------------------------------------
# Link state (pure, tested)
# ---------------------------------------------------------------------------

@dataclass
class LinkState:
    """Up/down bookkeeping. Times are time.monotonic(); `wall` is time.time().
    Every method returns a list of events (dicts) for the log, empty if nothing changed."""
    link: str = "no_device"          # "up" | "down" | "no_device"
    port: Optional[str] = None
    since: float = 0.0               # wall time of the last link change
    last_answer: Optional[float] = None
    last_stat: Optional[dict] = None
    rtt_ms: Optional[float] = None
    polls: int = 0
    answered: int = 0
    events: deque = field(default_factory=lambda: deque(maxlen=RECENT_EVENTS))

    def _change(self, new: str, wall: float, why: str) -> list[dict]:
        if new == self.link:
            return []
        old, self.link, self.since = self.link, new, wall
        ev = {"t": wall, "kind": "LINK", "text": f"{old} -> {new}: {why}"}
        self.events.append(ev)
        return [ev]

    def connected(self, port: str, now: float, wall: float) -> list[dict]:
        self.port = port
        self.last_answer = now                  # give the first poll a full window
        return self._change("up", wall, f"opened {port}")

    def lost(self, wall: float, why: str) -> list[dict]:
        self.port = None
        self.last_stat = None
        return self._change("no_device", wall, why)

    def poll_result(self, stat: Optional[dict], rtt_ms: Optional[float],
                    now: float, wall: float) -> list[dict]:
        self.polls += 1
        if stat is not None:
            self.answered += 1
            self.last_answer, self.last_stat, self.rtt_ms = now, stat, rtt_ms
            return self._change("up", wall, "answering")
        if self.last_answer is None or now - self.last_answer > DOWN_AFTER_S:
            return self._change("down", wall, f"no answer for {DOWN_AFTER_S:.0f} s")
        return []

    def pico_event(self, kind: str, text: str, wall: float) -> list[dict]:
        ev = {"t": wall, "kind": kind, "text": text}
        self.events.append(ev)
        return [ev]

    def snapshot(self, now: float, wall: float) -> dict:
        """The state file's contents."""
        s = self.last_stat
        return {
            "updated": wall,
            "link": self.link,
            "port": self.port,
            "since": self.since,
            "last_answer_age_s": None if self.last_answer is None else round(now - self.last_answer, 2),
            "rtt_ms": None if self.rtt_ms is None else round(self.rtt_ms, 1),
            "failsafe": None if s is None else s["age_ms"] > FAILSAFE_MS,
            "stat": s,
            "polls": self.polls,
            "answered": self.answered,
            "events": list(self.events),
        }


def write_state(path: Path, snap: dict) -> None:
    """Replace the state file in one step, so a reader never sees half a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(snap))
    os.replace(tmp, path)


class DailyLog:
    """Append-only JSON lines, one file per local day: data/pico/pico_YYYYMMDD.jsonl"""

    def __init__(self, log_dir: Path):
        self.dir = Path(log_dir)
        self.dir.mkdir(parents=True, exist_ok=True)

    def write(self, rec: dict) -> None:
        day = time.strftime("%Y%m%d", time.localtime(rec["t"]))
        with (self.dir / f"pico_{day}.jsonl").open("a") as f:
            f.write(json.dumps(rec) + "\n")


# ---------------------------------------------------------------------------
# The loop
# ---------------------------------------------------------------------------

def run(state_path: Path, log_dir: Path, every_s: float = 1.0,
        open_pico: Optional[Callable] = None, max_polls: Optional[int] = None,
        clock=time.monotonic, wall=time.time, sleep=time.sleep,
        say: Callable[[str], None] = print) -> LinkState:
    """Poll until stopped (or max_polls, for tests). Never raises on a lost link."""
    if open_pico is None:
        from forrest.drivers.pico import Pico
        open_pico = Pico
    st = LinkState(since=wall())
    log = DailyLog(log_dir)
    pico = None
    last_sample = -1e9

    def emit(events):
        for ev in events:
            log.write(ev)
            say(f"{time.strftime('%H:%M:%S', time.localtime(ev['t']))}  {ev['kind']:8s} {ev['text']}")

    try:
        while max_polls is None or st.polls < max_polls:
            if pico is None:
                try:
                    pico = open_pico()
                    emit(st.connected(pico.port or "?", clock(), wall()))
                except OSError as e:          # PicoError is a RuntimeError: handled below
                    emit(st.lost(wall(), f"can't open: {e}"))
                except RuntimeError as e:
                    emit(st.lost(wall(), str(e)))
                if pico is None:
                    st.polls += 1             # count the attempt so max_polls ends tests
                    write_state(state_path, st.snapshot(clock(), wall()))
                    sleep(RETRY_S)
                    continue

            t0 = clock()
            try:
                reply = pico.status()
            except OSError as e:              # unplugged (SerialException is an OSError)
                try:
                    pico.close()
                except OSError:
                    pass
                pico = None
                emit(st.lost(wall(), f"link lost: {e}"))
                write_state(state_path, st.snapshot(clock(), wall()))
                sleep(RETRY_S)
                continue

            now = clock()
            for r in list(pico.events):       # READY / FAILSAFE / BAD seen since the last poll
                emit(st.pico_event(r.kind, r.text, wall()))
            pico.events.clear()
            stat = reply.fields if reply is not None else None
            emit(st.poll_result(stat, 1000 * (now - t0) if stat else None, now, wall()))
            if stat is not None and now - last_sample >= LOG_SAMPLE_S:
                log.write({"t": wall(), "kind": "SAMPLE", "rtt_ms": st.rtt_ms, **stat})
                last_sample = now
            write_state(state_path, st.snapshot(now, wall()))
            sleep(max(0.0, every_s - (clock() - t0)))
    finally:
        if pico is not None:
            try:
                pico.close()
            except OSError:
                pass
    return st
