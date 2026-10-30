"""Serial link to a hoverboard mainboard running the EFeru FOC firmware.

This is the only module that talks to the drive board. On the bench it runs on
the Mac through the CP2102 adapter; later the Pico takes this job (B4) and the
Pi gets the same feedback through the Pico.

Protocol (EFeru hoverboard-firmware-hack-FOC, VARIANT_USART, 115200 8N1,
little-endian, 16-bit words):

  Command (8 bytes), Forrest -> board, must keep arriving or the board stops
  the wheels itself after SERIAL_TIMEOUT (~0.8 s):
      start 0xABCD | steer int16 | speed int16 | checksum = start ^ steer ^ speed
  With TANK_STEERING (Forrest's build), steer = LEFT wheel, speed = RIGHT
  wheel, each -1000..1000.

  Feedback (18 bytes), board -> Forrest, every 10 ms:
      start 0xABCD | cmd1 | cmd2 | speedR_meas | speedL_meas | batVoltage |
      boardTemp | cmdLed (uint16) | checksum = XOR of the eight words before it
  speeds in rpm, battery in V*100, temperature in degC*10.

Status: written from the firmware source (pinned in
firmware/hoverboard/prepare.sh) and unit-tested with synthetic bytes. Not yet
run on a real board -- H5/H6 in firmware/hoverboard/README.md are that test.
"""

from __future__ import annotations

import struct
import time
from dataclasses import asdict, dataclass
from typing import Iterator, List, Optional

BAUD = 115_200
START_FRAME = 0xABCD
START_BYTES = struct.pack("<H", START_FRAME)  # b"\xcd\xab"
CMD_MAX = 1000

_CMD = struct.Struct("<HhhH")
_FB = struct.Struct("<HhhhhhhHH")
COMMAND_LEN = _CMD.size     # 8
FEEDBACK_LEN = _FB.size     # 18


def _u16(x: int) -> int:
    return x & 0xFFFF


def clamp(v: int, lo: int = -CMD_MAX, hi: int = CMD_MAX) -> int:
    return max(lo, min(hi, int(v)))


def encode_command(left: int, right: int) -> bytes:
    """One command frame. Values are clamped to -1000..1000."""
    left, right = clamp(left), clamp(right)
    checksum = _u16(START_FRAME ^ _u16(left) ^ _u16(right))
    return _CMD.pack(START_FRAME, left, right, checksum)


@dataclass(frozen=True)
class Feedback:
    cmd_left: int          # command the board is applying (after its filter)
    cmd_right: int
    rpm_right: int         # measured wheel speed, signed, rpm
    rpm_left: int
    battery_v: float
    board_temp_c: float
    led: int
    t: float = 0.0         # host time when received (time.time())

    def as_record(self) -> dict:
        """Flat dict for the one log (and the Drive card)."""
        return {"src": "drive", **asdict(self)}


def decode_feedback(frame: bytes, t: float = 0.0) -> Optional[Feedback]:
    """Decode exactly one 18-byte frame; None if the start or checksum is wrong."""
    if len(frame) != FEEDBACK_LEN:
        return None
    start, c1, c2, sr, sl, bat, temp, led, checksum = _FB.unpack(frame)
    if start != START_FRAME:
        return None
    calc = 0
    for w in (start, c1, c2, sr, sl, bat, temp, led):
        calc ^= _u16(w)
    if calc != checksum:
        return None
    return Feedback(c1, c2, sr, sl, bat / 100.0, temp / 10.0, led, t)


class FeedbackParser:
    """Turns an arbitrary byte stream into Feedback frames, resyncing on junk."""

    def __init__(self) -> None:
        self.buf = bytearray()
        self.bad_frames = 0

    def feed(self, data: bytes, t: float = 0.0) -> List[Feedback]:
        self.buf += data
        out: List[Feedback] = []
        while True:
            i = self.buf.find(START_BYTES)
            if i < 0:
                # keep a trailing 0xCD: it may be the first half of a start frame
                del self.buf[: max(0, len(self.buf) - 1)]
                return out
            if i:
                del self.buf[:i]
            if len(self.buf) < FEEDBACK_LEN:
                return out
            fb = decode_feedback(bytes(self.buf[:FEEDBACK_LEN]), t)
            if fb is None:
                self.bad_frames += 1
                del self.buf[:1]          # slide one byte and look again
            else:
                out.append(fb)
                del self.buf[:FEEDBACK_LEN]


class Hoverboard:
    """Open link to the board. Use as a context manager.

    The board only moves while commands keep coming. `send()` is one frame;
    callers that drive the wheels must call it at a steady rate (20-50 Hz).
    On close, a few zero commands are sent so the wheels stop at once instead
    of waiting for the board's timeout.
    """

    def __init__(self, port: Optional[str] = None, baud: int = BAUD, serial_port=None):
        if serial_port is not None:
            self.ser = serial_port
        else:
            import serial  # pyserial
            self.ser = serial.Serial(port, baud, timeout=0)
        self.parser = FeedbackParser()
        self.latest: Optional[Feedback] = None

    def send(self, left: int, right: int) -> None:
        self.ser.write(encode_command(left, right))

    def stop(self, repeats: int = 3) -> None:
        for _ in range(repeats):
            self.send(0, 0)

    def poll(self) -> List[Feedback]:
        """Read whatever has arrived; return the complete frames."""
        waiting = getattr(self.ser, "in_waiting", 0) or 256
        data = self.ser.read(waiting)
        frames = self.parser.feed(data, time.time()) if data else []
        if frames:
            self.latest = frames[-1]
        return frames

    def iter_feedback(self, idle_sleep: float = 0.002) -> Iterator[Feedback]:
        while True:
            frames = self.poll()
            if not frames:
                time.sleep(idle_sleep)
            yield from frames

    def close(self) -> None:
        try:
            self.stop()
        finally:
            self.ser.close()

    def __enter__(self) -> "Hoverboard":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
