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
