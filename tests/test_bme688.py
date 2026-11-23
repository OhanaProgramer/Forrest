"""Host tests for the BME688 driver (firmware/pico/sensors/bme688.py), no hardware.

The regression numbers are one real reading from Jr's sensor (2026-11-23, Pico W,
0x77): 23.22 C / 41.29 %RH / 831.41 hPa / 15988 ohm, which matched the room
(about 1600 m elevation, so ~830 hPa is right).
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "firmware/pico/sensors"))
import bme688 as b  # noqa: E402

C1 = bytes.fromhex("536803103a8dbcd75800022332ff201e000022fa07f41e")
C2 = bytes.fromhex("3f5c2f002d14789c9d664edeb412")
C3 = bytes.fromhex("26aa164c13")
FIELD = bytes.fromhex("8000671260786b304fd18000000004787c")


def test_calibration_signedness():
    cal = b.parse_calibration(C1, C2, C3)
    assert (cal["t1"], cal["t2"], cal["t3"]) == (26269, 26707, 3)
    assert (cal["gh1"], cal["gh2"], cal["gh3"]) == (-76, -8626, 18)
    assert (cal["res_heat_val"], cal["res_heat_range"], cal["range_sw_err"]) == (38, 1, 1)
    assert cal["h1"] == (0x2F << 4) | (0x5C & 0x0F) and cal["h2"] == (0x3F << 4) | (0x5C >> 4)


def test_real_reading():
    r = b.parse_field(FIELD, b.parse_calibration(C1, C2, C3))
    assert r == {"temp_c": 23.22, "humidity_pct": 41.29, "pressure_hpa": 831.41,
                 "gas_ohm": 15988, "gas_low": False}


def test_no_new_data_is_none():
    assert b.parse_field(b"\x00" + FIELD[1:], b.parse_calibration(C1, C2, C3)) is None


def test_gas_pinned_at_full_scale_is_flagged():
    # the raw bytes seen before burn-in: 0xFF 0xFD = adc 1023, range 13, valid + stable
    r = b.parse_field(FIELD[:15] + b"\xff\xfd", b.parse_calibration(C1, C2, C3))
    assert r["gas_ohm"] == 5684 and r["gas_low"] is True


def test_gas_not_valid_or_not_stable_is_none():
    cal = b.parse_calibration(C1, C2, C3)
    assert b.parse_field(FIELD[:15] + b"\x6d\xec", cal)["gas_ohm"] is None  # heater off: not stable
    assert b.parse_field(FIELD[:15] + b"\x00\x04", cal)["gas_ohm"] is None  # no gas run


def test_heater_encoding():
    cal = b.parse_calibration(C1, C2, C3)
    assert b.heater_resistance(320, 23, cal) == 107       # as on the board
    assert b.heater_duration(150) == 0x65                 # 37 x 4 = 148 ms
    assert b.heater_duration(63) == 63
    assert b.heater_duration(5000) == 0xFF


class FakeI2C:
    def __init__(self, chip=0x61, variant=0x01):
        self.mem = {0xD0: chip, 0xF0: variant}
        for base, blob in ((0x8A, C1), (0xE1, C2), (0x00, C3), (0x1D, FIELD)):
            for i, v in enumerate(blob):
                self.mem[base + i] = v
        self.writes = []

    def readfrom_mem(self, addr, reg, n):
        return bytes(self.mem.get(reg + i, 0) for i in range(n))

    def writeto_mem(self, addr, reg, data):
        self.writes.append((reg, data[0]))


def test_trigger_then_collect_never_waits():
    i2c = FakeI2C()
    s = b.BME688(i2c)
    assert s.collect() is None                    # nothing triggered yet
    s.trigger()
    assert (0x74, s._ctrl_meas | 1) in i2c.writes  # forced mode
    assert (0x71, 0x20) in i2c.writes              # BME688 run_gas bit
    assert s.collect()["temp_c"] == 23.22 and s.ambient_c == 23.22


def test_wrong_chip_or_bme680_is_refused():
    with pytest.raises(OSError, match="chip id"):
        b.BME688(FakeI2C(chip=0x60))
    with pytest.raises(OSError, match="variant"):
        b.BME688(FakeI2C(variant=0x00))
