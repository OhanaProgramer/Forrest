"""The Pico monitor (forrest.health.pico_monitor), with a fake Pico and a fake clock."""
import json

import serial

from forrest.drivers import pico as pd
from forrest.health import pico_monitor as pm
from tests.test_pico_driver import Clock, FakePico


class Time:
    """One fake clock for monotonic, wall and sleep."""
    def __init__(self):
        self.t = 1_000.0

    def clock(self):
        return self.t

    def sleep(self, s):
        self.t += s


# -- LinkState -----------------------------------------------------------------

STAT = {"throttle": 0, "steer": 0, "esc_ns": 1499901, "steer_ns": 1499901,
        "age_ms": 9000, "max_gap_ms": 8, "trips": 1}


def test_link_up_down_and_back():
    st = pm.LinkState()
    assert [e["text"] for e in st.connected("/dev/ttyACM0", now=0, wall=100)] == \
        ["no_device -> up: opened /dev/ttyACM0"]
    assert st.poll_result(STAT, 5.0, now=1, wall=101) == []          # already up: no event
    assert st.poll_result(None, None, now=3, wall=103) == []         # 2 s silent: not yet
    ev = st.poll_result(None, None, now=4.5, wall=104.5)             # 3.5 s silent: down
    assert st.link == "down" and "no answer" in ev[0]["text"]
    assert st.poll_result(STAT, 6.0, now=5, wall=105)[0]["text"] == "down -> up: answering"
    assert (st.polls, st.answered) == (4, 2)


def test_snapshot_reports_failsafe_from_command_age():
    st = pm.LinkState()
    st.connected("p", now=0, wall=0)
    st.poll_result(STAT, 5.0, now=1, wall=1)
    snap = st.snapshot(now=1.5, wall=1.5)
    assert snap["link"] == "up" and snap["failsafe"] is True
    assert snap["last_answer_age_s"] == 0.5 and snap["rtt_ms"] == 5.0
    st.poll_result({**STAT, "age_ms": 40}, 5.0, now=2, wall=2)       # a controller feeding it
    assert st.snapshot(now=2, wall=2)["failsafe"] is False


def test_recent_events_are_capped():
    st = pm.LinkState()
    for i in range(50):
        st.pico_event("BAD", f"BAD {i}", wall=i)
    assert len(st.events) == pm.RECENT_EVENTS and st.events[-1]["text"] == "BAD 49"


# -- the loop --------------------------------------------------------------------

def make_opener(fakes):
    """Each call opens the next fake; an exception in the list is raised instead."""
    it = iter(fakes)

    def open_pico():
        f = next(it)
        if isinstance(f, Exception):
            raise f
        p = pd.Pico(serial_port=f, clock=Clock())   # driver waits on its own ticking clock
        p.port = "/dev/ttyACM0"
        return p
    return open_pico


def run(tmp_path, fakes, polls):
    t = Time()
    lines = []
    st = pm.run(tmp_path / "pico.json", tmp_path / "log", every_s=1.0,
                open_pico=make_opener(fakes), max_polls=polls,
                clock=t.clock, wall=t.clock, sleep=t.sleep, say=lines.append)
    state = json.loads((tmp_path / "pico.json").read_text())
    log = [json.loads(l) for f in sorted((tmp_path / "log").glob("*.jsonl"))
           for l in f.read_text().splitlines()]
    return st, state, log, lines


def test_polls_read_only_and_logs_events(tmp_path):
    fake = FakePico(b"READY\nFAILSAFE 1499901\n")
    st, state, log, _ = run(tmp_path, [fake], polls=12)
    assert set(fake.written) == {"?"}                                 # never a drive command
    assert state["link"] == "up" and state["answered"] == 12
    assert state["failsafe"] is True                                  # FakePico reports age 600 ms > 500
    kinds = [r["kind"] for r in log]
    assert kinds[:3] == ["LINK", "READY", "FAILSAFE"]
    assert kinds.count("SAMPLE") == 2                                 # t=0 and t=10 s of 12 s


def test_no_device_then_plugged_in(tmp_path):
    st, state, log, _ = run(tmp_path, [pd.PicoError("no Pico found on USB"), FakePico()], polls=3)
    assert state["link"] == "up"
    texts = [r["text"] for r in log if r["kind"] == "LINK"]
    assert texts == ["no_device -> up: opened /dev/ttyACM0"]          # no_device at start isn't a change


def test_unplug_mid_run_reconnects(tmp_path):
    class Unplugs(FakePico):
        n = 0

        def write(self, b):
            Unplugs.n += 1
            if Unplugs.n == 3:
                raise serial.SerialException("device disconnected?")
            super().write(b)

    st, state, log, _ = run(tmp_path, [Unplugs(), FakePico()], polls=6)
    texts = [r["text"] for r in log if r["kind"] == "LINK"]
    assert texts[0].startswith("no_device -> up")
    assert texts[1].startswith("up -> no_device: link lost")
    assert texts[2].startswith("no_device -> up")
    assert state["link"] == "up"


def test_silent_pico_goes_down(tmp_path):
    class Silent(FakePico):
        def write(self, b):
            self.written.append(b.decode().strip())

    st, state, log, _ = run(tmp_path, [Silent()], polls=6)
    assert state["link"] == "down" and state["answered"] == 0
    assert any("no answer" in r["text"] for r in log if r["kind"] == "LINK")
