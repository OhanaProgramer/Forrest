"""Drive LidarC1.iter_scans with a fake serial port, including a corrupted byte."""

import struct

from forrest.drivers.lidar_c1 import LidarC1
from tests.test_lidar_protocol import make_sample


class FakeSerial:
    def __init__(self, data: bytes):
        self.data = bytearray(data)
        self.written = bytearray()

    def write(self, b):
        self.written += b

    def read(self, n):
        out, self.data = bytes(self.data[:n]), self.data[n:]
        return out

    def reset_input_buffer(self):
        pass

    def close(self):
        pass


def rotation(n, start_angle=0.0):
    return b"".join(
        make_sample(start_angle + i * (360 / n), 1.0 + i * 0.01, new_rotation=(i == 0))
        for i in range(n)
    )


def test_iter_scans_groups_rotations_and_resyncs():
    descriptor = bytes([0xA5, 0x5A]) + struct.pack("<I", 5 | (1 << 30)) + bytes([0x81])
    junk = b"\x00"  # one stray byte mid-stream; the driver must slide past it
    stream = descriptor + rotation(10) + junk + rotation(12) + rotation(8)
    lidar = LidarC1(serial_port=FakeSerial(stream))

    scans = []
    it = lidar.iter_scans()
    scans.append(next(it))
    scans.append(next(it))

    assert lidar._serial.written.startswith(bytes([0xA5, 0x20]))
    assert len(scans[0].points) == 10
    assert len(scans[1].points) == 12


class SpinUpSerial(FakeSerial):
    """Like the real C1: the descriptor at once, then `silent_reads` empty reads
    (each a 1 s serial timeout on the real port) before samples flow."""
    def __init__(self, data, silent_reads, clock):
        super().__init__(data)
        self.silent, self.clock = silent_reads, clock

    def read(self, n):
        if len(self.data) and self.written and self.silent and self.data[:2] != b"\xa5\x5a":
            self.silent -= 1
            self.clock.t += 1.0
            return b""
        return super().read(n)


class Clock:
    t = 0.0
    def __call__(self):
        return self.t


DESCRIPTOR = bytes([0xA5, 0x5A]) + struct.pack("<I", 5 | (1 << 30)) + bytes([0x81])


def test_waits_for_motor_spin_up_before_the_first_sample():
    clock = Clock()
    fake = SpinUpSerial(DESCRIPTOR + rotation(10) + rotation(10), silent_reads=2, clock=clock)
    scan = next(LidarC1(serial_port=fake, clock=clock).iter_scans())   # 2 s of silence: fine
    assert len(scan.points) == 10


def test_gives_up_if_no_sample_within_the_spin_up_limit():
    import pytest
    from forrest.drivers.lidar_c1 import LidarError, SPINUP_TIMEOUT_S
    clock = Clock()
    fake = SpinUpSerial(DESCRIPTOR + rotation(10), silent_reads=99, clock=clock)
    with pytest.raises(LidarError, match="timed out"):
        next(LidarC1(serial_port=fake, clock=clock).iter_scans())
    assert SPINUP_TIMEOUT_S <= clock.t <= SPINUP_TIMEOUT_S + 1.0
