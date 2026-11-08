"""The Pi-side Pico driver (forrest.drivers.pico) against a fake serial port."""
from types import SimpleNamespace

import pytest

from forrest.drivers import pico as pd


# -- parse_reply ---------------------------------------------------------------

def test_parse_stat_with_and_without_trips():
    r = pd.parse_reply("STAT 300 0 1649861 1499901 148 16 3", t=1.5)
    assert r.kind == "STAT" and r.t == 1.5
    assert r.fields == {"throttle": 300, "steer": 0, "esc_ns": 1649861, "steer_ns": 1499901,
                        "age_ms": 148, "max_gap_ms": 16, "trips": 3}
    old = pd.parse_reply("STAT 0 0 1499901 1499901 549 6")      # pre-2026-11-08 firmware
    assert old.kind == "STAT" and "trips" not in old.fields


def test_parse_other_kinds():
    assert pd.parse_reply("READY").kind == "READY"
    assert pd.parse_reply("FAILSAFE 1499901\r").fields == {"esc_ns": 1499901}
    assert pd.parse_reply("OK 250 -100 1625122 1450118").fields["steer"] == -100
    bad = pd.parse_reply("BAD hello world")
    assert bad.kind == "BAD" and bad.fields == {"line": "hello world"}


@pytest.mark.parametrize("line", ["", "   ", "STAT 1 2", "STAT a b c d e f",
                                  "OK 1 2 3 4 5", "READY now", "WHAT 1",
                                  "MicroPython v1.29.0 on 2026-08-24"])
def test_parse_never_raises(line):
    assert pd.parse_reply(line).kind == "UNKNOWN"


def test_format_command():
    assert pd.format_command(250, -100) == "250,-100"
    with pytest.raises(ValueError):
        pd.format_command(1001, 0)
    with pytest.raises(TypeError):
        pd.format_command(0.5, 0)
    with pytest.raises(TypeError):
        pd.format_command(True, 0)


def test_find_port():
    ports = [SimpleNamespace(device="/dev/ttyUSB0", vid=0x10C4, pid=0xEA60),   # LIDAR adapter
             SimpleNamespace(device="/dev/ttyACM0", vid=0x2E8A, pid=0x0005)]
    assert pd.find_port(ports) == "/dev/ttyACM0"
    assert pd.find_port(ports[:1]) is None


# -- the device, with a fake port ----------------------------------------------

class FakePico:
    """Answers like the firmware: "?" -> STAT, a command -> OK."""

    def __init__(self, preload=b""):
        self.rx = bytearray(preload)    # bytes waiting for the Pi to read
        self.written = []

    @property
    def in_waiting(self):
        return len(self.rx)

    def write(self, b):
        line = b.decode().strip()
        self.written.append(line)
        if line == "?":
            self.rx += b"STAT 0 0 1499901 1499901 600 9 1\n"
        elif "," in line:
            t, s = line.split(",")
            self.rx += f"OK {t} {s} 1600000 1500000\n".encode()

    def read(self, n):
        out, self.rx = bytes(self.rx[:n]), self.rx[n:]
        return out

    def close(self):
        pass


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        self.t += 0.01
        return self.t


def make(preload=b"", fake=None):
    fake = fake or FakePico(preload)
    return pd.Pico(serial_port=fake, clock=Clock()), fake


def test_status_answers_and_keeps_other_lines_as_events():
    p, fake = make(b"READY\nFAILSAFE 1499901\n")
    stat = p.status()
    assert stat.kind == "STAT" and stat.fields["trips"] == 1
    assert fake.written == ["?"]                          # a poll never sends a command
    assert [e.kind for e in p.events] == ["READY", "FAILSAFE"]
    assert p.last_rx is not None


def test_status_times_out_when_pico_is_silent():
    class Silent(FakePico):
        def write(self, b):
            self.written.append(b.decode().strip())
    p, _ = make(fake=Silent())
    assert p.status(timeout_s=0.1) is None


def test_send_command_is_validated_and_answered():
    p, fake = make()
    ok = p.send_command(250, -100)
    assert ok.kind == "OK" and ok.fields["throttle"] == 250
    assert fake.written == ["250,-100"]
    with pytest.raises(ValueError):
        p.send_command(5000, 0)
    assert fake.written == ["250,-100"]                   # nothing sent for the bad one


def test_half_line_waits_for_its_newline():
    p, fake = make(b"FAILSAFE 14")
    assert p.drain() == []
    fake.rx += b"99901\n"
    assert [r.fields for r in p.drain()] == [{"esc_ns": 1499901}]


def test_no_newline_junk_is_dropped():
    p, fake = make(b"x" * 5000)
    for _ in range(10):
        p.drain()
    fake.rx += b"READY\n"
    assert [r.kind for r in p.drain()] == ["READY"]


def test_send_line_refuses_embedded_newlines():
    p, _ = make()
    with pytest.raises(ValueError):
        p._send_line("?\n0,0")
