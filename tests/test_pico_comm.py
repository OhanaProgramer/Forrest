"""Host tests for the Pico serial line handling (firmware/pico/drive/comm.py)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "firmware/pico/drive"))
import comm  # noqa: E402


def feed(buf, text):
    return [line for ch in text if (line := buf.push(ch)) is not None]


def test_whole_lines():
    b = comm.LineBuffer()
    assert feed(b, "250,-100\n?\n") == ["250,-100", "?"]


def test_partial_line_waits_for_newline():
    b = comm.LineBuffer()
    assert feed(b, "250,") == []           # half a line: nothing yet, no blocking
    assert feed(b, "-100\n") == ["250,-100"]


def test_crlf_and_blank_lines():
    b = comm.LineBuffer()
    assert feed(b, "0,0\r\n\r\n\n1,1\r") == ["0,0", "1,1"]


def test_overflow_is_reported_once_then_recovers():
    b = comm.LineBuffer(max_line=8)
    assert feed(b, "x" * 50 + "\n") == [comm.OVERFLOW]
    assert feed(b, "0,0\n") == ["0,0"]


def test_format_msg():
    assert comm.format_msg("OK", 250, -100, 1750000) == "OK 250 -100 1750000"
    assert comm.format_msg("READY") == "READY"
