"""Driver for the Pico 2 drive controller (firmware/pico/drive/).

The Pi's half of the USB serial link. The only module on the Pi that talks to
the Pico. It sends lines and turns the Pico's replies into data:

    READY                                    after the Pico boots
    OK t s esc_ns steer_ns                   a drive command was taken
    BAD <line>                               the Pico rejected a line
    FAILSAFE esc_ns                          the heartbeat tripped; throttle cut
    STAT t s esc_ns steer_ns age_ms max_gap_ms [trips]   reply to "?"

The line protocol itself is documented at the top of firmware/pico/drive/main.py;
keep the two in step.

Two directions of "is it alive?":
  * Pi -> Pico: drive commands are the heartbeat. Only a controller sends them
    (`send_command`). The monitor never does, so the Pico stays in failsafe.
  * Pico -> Pi: `status()` sends "?" and waits for STAT. No reply = link down.

Which board: picked by USB serial number (BOARDS below), never by USB id alone,
so a second Pico (the sensor board) can share the USB bus safely.

Status: bench-tested against the Pico 2 on 2026-11-08 (no ESC or servo wired).
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Callable, Optional

DEFAULT_BAUD = 115_200          # ignored by USB CDC, but pyserial needs a value
PICO_VID, MICROPYTHON_PID = 0x2E8A, 0x0005
CMD_LIMIT = 1000                # matches firmware protocol.CMD_MAX
STARTUP_SETTLE_S = 0.2          # drop whatever arrives right after opening (see open note)

# Which Pico is which, by USB serial number. Every board running MicroPython
# reports the same USB id (2e8a:0005), so with two Picos plugged in the id
# alone can't tell them apart. The serial number is the flash chip's unique id
# (machine.unique_id()) and doesn't change while the board runs MicroPython.
# Other firmware may report a different one: under Arduino the Pico W showed
# 086461E639740B43, so re-check with `forrest pico list` after a reflash. Find it with `forrest pico list` (or
# `mpremote devs`). A board must be listed here before the Pi will open it.
BOARDS = {
    "drive": "1c4e1cea890aaffb",    # Pico 2 (RP2350), firmware/pico/drive/, since 2026-11-08
    "sensors": "e6616408430b7439",  # Pico W (RP2040), sensor board, MicroPython 1.29.0, since 2026-11-10
}
DEFAULT_BOARD = "drive"


class PicoError(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# Replies (pure, tested)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Reply:
    """One line from the Pico. `kind` is READY / OK / BAD / FAILSAFE / STAT /
    UNKNOWN; `fields` holds the parsed numbers by name; `t` is the Pi's clock
    (time.monotonic) when the line arrived."""
    kind: str
    fields: dict = field(default_factory=dict)
    text: str = ""
    t: float = 0.0


_NUMERIC = {
    "OK": ("throttle", "steer", "esc_ns", "steer_ns"),
    "FAILSAFE": ("esc_ns",),
    "STAT": ("throttle", "steer", "esc_ns", "steer_ns", "age_ms", "max_gap_ms", "trips"),
}
_OPTIONAL_TAIL = {"STAT": 1}    # "trips" arrived with the modular firmware (2026-11-08)


def parse_reply(line: str, t: float = 0.0) -> Reply:
    """One line from the Pico -> Reply. Never raises: anything it can't read
    comes back as UNKNOWN, with the text kept for the log."""
    text = line.strip()
    if not text:
        return Reply("UNKNOWN", text=text, t=t)
    tag, _, rest = text.partition(" ")
    if tag == "READY" and not rest:
        return Reply("READY", text=text, t=t)
    if tag == "BAD":
        return Reply("BAD", {"line": rest}, text=text, t=t)
    names = _NUMERIC.get(tag)
    if names is None:
        return Reply("UNKNOWN", text=text, t=t)
    parts = rest.split()
    need = len(names) - _OPTIONAL_TAIL.get(tag, 0)
    if not need <= len(parts) <= len(names):
        return Reply("UNKNOWN", text=text, t=t)
    try:
        values = [int(p) for p in parts]
    except ValueError:
        return Reply("UNKNOWN", text=text, t=t)
    return Reply(tag, dict(zip(names, values)), text=text, t=t)


def format_command(throttle: int, steer: int) -> str:
    """A drive command line. Refuses out-of-range values rather than letting
    the Pico clamp them: a bad number here is a bug on the Pi."""
    for name, v in (("throttle", throttle), ("steer", steer)):
        if not isinstance(v, int) or isinstance(v, bool):
            raise TypeError(f"{name} must be an int, got {v!r}")
        if not -CMD_LIMIT <= v <= CMD_LIMIT:
            raise ValueError(f"{name} {v} outside ±{CMD_LIMIT}")
    return f"{throttle},{steer}"


def micropython_ports(ports) -> list:
    """The ports that are MicroPython boards (USB id 2e8a:0005), from
    serial.tools.list_ports.comports() output (anything with .device / .vid /
    .pid / .serial_number)."""
    return [p for p in ports
            if getattr(p, "vid", None) == PICO_VID and getattr(p, "pid", None) == MICROPYTHON_PID]


def role_of(serial: Optional[str]) -> Optional[str]:
    """Which entry in BOARDS a serial number belongs to, or None."""
    if not serial:
        return None
    for role, known in BOARDS.items():
        if known.lower() == serial.lower():
            return role
    return None


def find_port(ports, serial: str) -> Optional[str]:
    """The device path of the MicroPython board with this USB serial number,
    or None. Never falls back to "any Pico": with two boards on USB that would
    hand a drive controller the sensor board, or the other way round."""
    for p in micropython_ports(ports):
        if (getattr(p, "serial_number", None) or "").lower() == serial.lower():
            return p.device
    return None


def board_port(ports, board: str = DEFAULT_BOARD) -> str:
    """Device path for a named board (a key of BOARDS). Raises PicoError with
    what *is* plugged in when the board isn't there."""
    if board not in BOARDS:
        raise PicoError(f"unknown board {board!r}; known: {', '.join(BOARDS)}")
    port = find_port(ports, BOARDS[board])
    if port is not None:
        return port
    seen = [f"{p.device} (serial {getattr(p, 'serial_number', None)}, "
            f"{role_of(getattr(p, 'serial_number', None)) or 'not in BOARDS'})"
            for p in micropython_ports(ports)]
    raise PicoError(f"{board} Pico (serial {BOARDS[board]}) not on USB; "
                    f"MicroPython boards seen: {', '.join(seen) or 'none'}")


# ---------------------------------------------------------------------------
# The device
# ---------------------------------------------------------------------------

class Pico:
    """Live Pico on a USB serial port. Use as a context manager:

        with Pico() as pico:              # finds the drive board by serial number
            stat = pico.status()          # Reply("STAT", ...) or None
            for r in pico.events: ...     # READY / FAILSAFE / BAD seen so far

    Only one program may hold the port (it is opened exclusive). Every reply
    that isn't the answer to a call lands in `events`, so a monitor can log
    failsafe trips that happen between polls.
    """

    def __init__(self, port: Optional[str] = None, board: str = DEFAULT_BOARD,
                 timeout: float = 0.05,
                 serial_port=None, clock: Callable[[], float] = time.monotonic,
                 settle_s: float = STARTUP_SETTLE_S, max_events: int = 1000):
        self._clock = clock
        if serial_port is None:
            import serial  # imported here so tests run without pyserial
            from serial.tools import list_ports

            if port is None:                    # an explicit port skips the serial check
                port = board_port(list_ports.comports(), board)
            # exclusive: a second program can't open it and steal replies.
            serial_port = serial.Serial(port, DEFAULT_BAUD, timeout=timeout, exclusive=True)
            # Opening the tty echoes the Pico's queued output back to it for a
            # moment, before pyserial switches the port to raw mode (the Pico
            # then logs "BAD READY"). Let that settle and drop it.
            time.sleep(settle_s)
            serial_port.reset_input_buffer()
        self.port = port
        self.board = board
        self._serial = serial_port
        self._buf = bytearray()
        self.events: deque[Reply] = deque(maxlen=max_events)
        self.last_rx: Optional[float] = None    # clock time of the last line received

    def __enter__(self) -> "Pico":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def close(self) -> None:
        self._serial.close()

    # -- lines -------------------------------------------------------------
    def _send_line(self, line: str) -> None:
        if "\n" in line or "\r" in line:
            raise ValueError("one line at a time")
        self._serial.write(line.encode("ascii") + b"\n")

    def read_replies(self) -> list[Reply]:
        """Whatever complete lines have arrived (waits at most one read timeout).
        A half line stays buffered until its newline comes."""
        chunk = self._serial.read(max(1, getattr(self._serial, "in_waiting", 0) or 0))
        if chunk:
            self._buf += chunk
        out = []
        while True:
            nl = self._buf.find(b"\n")
            if nl < 0:
                break
            raw, self._buf = bytes(self._buf[:nl]), self._buf[nl + 1:]
            text = raw.decode("ascii", errors="replace").strip()
            if text:
                now = self._clock()
                self.last_rx = now
                out.append(parse_reply(text, t=now))
        if len(self._buf) > 4096:         # no newline in 4 KB: junk, start over
            self._buf.clear()
        return out

    def _wait_for(self, kind: str, timeout_s: float) -> Optional[Reply]:
        deadline = self._clock() + timeout_s
        while self._clock() < deadline:
            for r in self.read_replies():
                if r.kind == kind:
                    return r
                self.events.append(r)
        return None

    # -- calls ---------------------------------------------------------------
    def status(self, timeout_s: float = 0.5) -> Optional[Reply]:
        """Ask "?" and wait for STAT. None means the Pico didn't answer in time.
        Does not feed the Pico's heartbeat."""
        self._send_line("?")
        return self._wait_for("STAT", timeout_s)

    def send_command(self, throttle: int, steer: int, timeout_s: float = 0.5) -> Optional[Reply]:
        """Send one drive command and wait for OK. This IS the heartbeat: only
        a controller calls it. The Pico cuts throttle 500 ms after the last one."""
        self._send_line(format_command(throttle, steer))
        return self._wait_for("OK", timeout_s)

    def drain(self) -> list[Reply]:
        """Read whatever is waiting into `events`; returns the new ones."""
        new = self.read_replies()
        self.events.extend(new)
        return new
