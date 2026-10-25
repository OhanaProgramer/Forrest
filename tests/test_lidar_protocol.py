"""Protocol parsing tests: synthetic bytes, no hardware."""

import struct

import pytest

from forrest.drivers.lidar_c1 import (
    LidarError, parse_descriptor, parse_health, parse_info, parse_sample,
)


def make_sample(angle_deg, distance_m, quality=47, new_rotation=False):
    """Build the 5 bytes the LIDAR would send for one point."""
    s = 1 if new_rotation else 0
    b0 = (quality << 2) | ((1 - s) << 1) | s
    angle_q6 = int(round(angle_deg * 64))
    b1 = ((angle_q6 & 0x7F) << 1) | 0x01
    b2 = angle_q6 >> 7
    dist_q2 = int(round(distance_m * 1000 * 4))
    return bytes([b0, b1, b2, dist_q2 & 0xFF, dist_q2 >> 8])


def test_scan_descriptor():
    # length 5, send mode 1 (multiple responses), type 0x81
    raw = bytes([0xA5, 0x5A]) + struct.pack("<I", 5 | (1 << 30)) + bytes([0x81])
    assert parse_descriptor(raw) == (5, 1, 0x81)


def test_bad_descriptor_raises():
    with pytest.raises(LidarError):
        parse_descriptor(bytes(7))


def test_sample_roundtrip():
    new, p = parse_sample(make_sample(123.45, 1.234, quality=40, new_rotation=True))
    assert new is True
    assert p.angle_deg == pytest.approx(123.45, abs=1 / 64)
    assert p.distance_m == pytest.approx(1.234, abs=0.001)
    assert p.quality == 40


def test_sample_out_of_sync_is_rejected():
    raw = bytearray(make_sample(10, 1.0))
    raw[0] |= 0b11  # start and inverse-start both set: impossible
    assert parse_sample(bytes(raw)) is None
    raw = bytearray(make_sample(10, 1.0))
    raw[1] &= 0xFE  # check bit cleared
    assert parse_sample(bytes(raw)) is None


def test_health_and_info():
    assert parse_health(bytes([0, 0, 0])).status == "good"
    assert parse_health(bytes([2, 0x34, 0x12])).error_code == 0x1234
    info = parse_info(bytes([0x41, 1, 1, 18]) + bytes(range(16)))
    assert info.firmware == "1.01"
    assert info.serial == bytes(range(16)).hex().upper()
