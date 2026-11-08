"""Host tests for the Pico command parser (firmware/pico/drive/protocol.py)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "firmware/pico/drive"))
import protocol as p  # noqa: E402


def test_parse_valid_and_clamped():
    assert p.parse_command("250,-100") == (250, -100)
    assert p.parse_command(" 0,0\r\n") == (0, 0)
    assert p.parse_command("5000,-5000") == (1000, -1000)


def test_parse_rejects_bad_lines():
    for bad in ["", "?", "1", "1,2,3", "a,b", "1.5,2", None]:
        assert p.parse_command(bad) is None


def test_pulse_mapping():
    assert p.cmd_to_pulse_ns(0) == 1_500_000
    assert p.cmd_to_pulse_ns(1000) == 2_000_000
    assert p.cmd_to_pulse_ns(-1000) == 1_000_000
    assert p.cmd_to_pulse_ns(500) == 1_750_000
    assert p.cmd_to_pulse_ns(9999) == 2_000_000
