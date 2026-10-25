"""Driver for the Slamtec RPLIDAR C1 (model C1M1-R2).

This is the only module that talks to the LIDAR hardware. Everything else asks
for scans through `ScanSource` (see forrest.sensing.scan), so the same code can
run against a live LIDAR on the Pi or a recording replayed on the Mac.

Protocol: the standard RPLIDAR serial protocol (request = 0xA5 + command byte;
response = 7-byte descriptor starting 0xA5 0x5A, then data). The C1 talks
3.3 V UART at 460800 baud, 8N1, either through the USB-C adapter board
(shows up as /dev/ttyUSB0 or similar) or wired directly to a UART.

Datasheet notes that matter here:
  * 5 V supply, ~800 mA at motor start, ~230 mA running. The Pi limits USB to
    600 mA total unless `usb_max_current_enable=1` is in config.txt.
  * Typical scan rate 10 Hz (8-12 Hz), ~5,000 samples/s, 0.72 deg resolution.

Status: written against the published protocol and unit-tested with synthetic
bytes. Not yet run against the real unit -- B1 is that test.
"""

from __future__ import annotations

import struct
import time
from dataclasses import dataclass
from typing import Iterator, Optional

from forrest.sensing.scan import Scan, ScanPoint

DEFAULT_BAUD = 460_800

# Request bytes
SYNC = 0xA5
CMD_STOP = 0x25
CMD_RESET = 0x40
CMD_SCAN = 0x20
CMD_GET_INFO = 0x50
CMD_GET_HEALTH = 0x52

# Response descriptor
DESCRIPTOR_SYNC = (0xA5, 0x5A)
DESCRIPTOR_LEN = 7
TYPE_SCAN = 0x81
TYPE_INFO = 0x04
TYPE_HEALTH = 0x06

SAMPLE_LEN = 5
HEALTH_STATUS = {0: "good", 1: "warning", 2: "error"}


class LidarError(RuntimeError):
    """Raised when the LIDAR answers with something we don't expect."""


@dataclass(frozen=True)
class DeviceInfo:
    model: int
    firmware: str
    hardware: int
    serial: str


@dataclass(frozen=True)
class Health:
    status: str
    error_code: int


# ---------------------------------------------------------------------------
# Pure parsing helpers (no hardware needed; these are what the tests cover)
# ---------------------------------------------------------------------------

def parse_descriptor(raw: bytes) -> tuple[int, int, int]:
    """Return (data_length, send_mode, data_type) from a 7-byte descriptor."""
    if len(raw) != DESCRIPTOR_LEN or tuple(raw[:2]) != DESCRIPTOR_SYNC:
        raise LidarError(f"bad response descriptor: {raw.hex()}")
    size_and_mode = struct.unpack("<I", raw[2:6])[0]
    length = size_and_mode & 0x3FFFFFFF
    mode = size_and_mode >> 30
    return length, mode, raw[6]


def parse_info(data: bytes) -> DeviceInfo:
    if len(data) != 20:
        raise LidarError(f"info payload should be 20 bytes, got {len(data)}")
    model, fw_minor, fw_major, hardware = data[0], data[1], data[2], data[3]
    return DeviceInfo(
        model=model,
        firmware=f"{fw_major}.{fw_minor:02d}",
        hardware=hardware,
        serial=data[4:20].hex().upper(),
    )


def parse_health(data: bytes) -> Health:
    if len(data) != 3:
        raise LidarError(f"health payload should be 3 bytes, got {len(data)}")
    status = HEALTH_STATUS.get(data[0], f"unknown({data[0]})")
    return Health(status=status, error_code=struct.unpack("<H", data[1:3])[0])


def parse_sample(raw: bytes) -> Optional[tuple[bool, ScanPoint]]:
    """Decode one 5-byte scan sample.

    Returns (is_new_rotation, point), or None if the check bits say the
    bytes are out of sync (the caller should then resynchronise).
    """
    b0, b1 = raw[0], raw[1]
    start = b0 & 0x01
    inverse_start = (b0 >> 1) & 0x01
    if start == inverse_start:          # these two bits must always differ
        return None
    if not (b1 & 0x01):                 # check bit must be 1
        return None
    quality = b0 >> 2
    angle_q6 = (b1 >> 1) | (raw[2] << 7)
    distance_q2 = raw[3] | (raw[4] << 8)
    point = ScanPoint(
        angle_deg=angle_q6 / 64.0,
        distance_m=distance_q2 / 4.0 / 1000.0,
        quality=quality,
    )
    return bool(start), point


# ---------------------------------------------------------------------------
# The device
# ---------------------------------------------------------------------------

class LidarC1:
    """Live RPLIDAR C1 on a serial port. Use as a context manager:

        with LidarC1("/dev/ttyUSB0") as lidar:
            print(lidar.info(), lidar.health())
            for scan in lidar.iter_scans():
                ...
    """

    def __init__(self, port: str = "/dev/ttyUSB0", baud: int = DEFAULT_BAUD,
                 timeout: float = 1.0, serial_port=None):
        if serial_port is None:
            import serial  # imported here so tests run without pyserial

            serial_port = serial.Serial(port, baud, timeout=timeout)
        self._serial = serial_port  # tests pass a fake with the same methods
        self._scanning = False

    # -- context manager -------------------------------------------------
    def __enter__(self) -> "LidarC1":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def close(self) -> None:
        try:
            self.stop()
        finally:
            self._serial.close()

    # -- low level -------------------------------------------------------
    def _send(self, cmd: int) -> None:
        self._serial.write(bytes([SYNC, cmd]))

    def _read_exact(self, n: int) -> bytes:
        data = self._serial.read(n)
        if len(data) != n:
            raise LidarError(f"timed out: wanted {n} bytes, got {len(data)}")
        return data

    def _request(self, cmd: int, expected_type: int) -> bytes:
        self._serial.reset_input_buffer()
        self._send(cmd)
        length, _mode, dtype = parse_descriptor(self._read_exact(DESCRIPTOR_LEN))
        if dtype != expected_type:
            raise LidarError(f"expected data type {expected_type:#x}, got {dtype:#x}")
        return self._read_exact(length)

    # -- commands ----------------------------------------------------------
    def info(self) -> DeviceInfo:
        return parse_info(self._request(CMD_GET_INFO, TYPE_INFO))

    def health(self) -> Health:
        return parse_health(self._request(CMD_GET_HEALTH, TYPE_HEALTH))

    def stop(self) -> None:
        self._send(CMD_STOP)
        self._scanning = False
        time.sleep(0.01)  # protocol asks for >=1 ms before the next request
        self._serial.reset_input_buffer()

    def reset(self) -> None:
        self._send(CMD_RESET)
        self._scanning = False
        time.sleep(0.5)
        self._serial.reset_input_buffer()

    def iter_scans(self, min_quality: int = 1) -> Iterator[Scan]:
        """Yield one Scan per full rotation, forever (until the caller stops)."""
        self._serial.reset_input_buffer()
        self._send(CMD_SCAN)
        length, _mode, dtype = parse_descriptor(self._read_exact(DESCRIPTOR_LEN))
        if dtype != TYPE_SCAN or length != SAMPLE_LEN:
            raise LidarError(f"unexpected scan descriptor: len={length} type={dtype:#x}")
        self._scanning = True

        points: list[ScanPoint] = []
        started = False
        raw = self._read_exact(SAMPLE_LEN)
        while self._scanning:
            decoded = parse_sample(raw)
            if decoded is None:
                # Out of sync: slide the window by one byte and try again.
                raw = raw[1:] + self._read_exact(1)
                continue
            raw = self._read_exact(SAMPLE_LEN)
            new_rotation, point = decoded
            if new_rotation:
                if started and points:
                    yield Scan(timestamp=time.time(), points=points)
                points = []
                started = True
            if started and point.quality >= min_quality and point.distance_m > 0:
                points.append(point)
