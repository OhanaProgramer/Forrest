"""Hoverboard serial protocol: command encoding, feedback decoding, resync."""

import struct

from forrest.drivers.hoverboard import (
    COMMAND_LEN, FEEDBACK_LEN, FeedbackParser, Hoverboard, decode_feedback,
    encode_command,
)


def make_feedback(cmd1=0, cmd2=0, sr=0, sl=0, bat=3700, temp=250, led=0, corrupt=False):
    words = [0xABCD, cmd1, cmd2, sr, sl, bat, temp, led]
    checksum = 0
    for w in words:
        checksum ^= w & 0xFFFF
    if corrupt:
        checksum ^= 1
    return struct.pack("<HhhhhhhHH", *words, checksum)


def test_sizes_match_firmware_structs():
    assert COMMAND_LEN == 8
    assert FEEDBACK_LEN == 18


def test_encode_command_layout_and_checksum():
    frame = encode_command(100, -50)
    start, left, right, checksum = struct.unpack("<HhhH", frame)
    assert start == 0xABCD and left == 100 and right == -50
    assert checksum == (0xABCD ^ 100 ^ (-50 & 0xFFFF))
    assert frame[:2] == b"\xcd\xab"          # little-endian start frame


def test_encode_command_clamps():
    _, left, right, _ = struct.unpack("<HhhH", encode_command(5000, -5000))
    assert (left, right) == (1000, -1000)


def test_decode_feedback_units():
    fb = decode_feedback(make_feedback(cmd1=50, cmd2=-50, sr=-12, sl=13, bat=3712, temp=284))
    assert fb is not None
    assert (fb.cmd_left, fb.cmd_right, fb.rpm_right, fb.rpm_left) == (50, -50, -12, 13)
    assert fb.battery_v == 37.12
    assert fb.board_temp_c == 28.4


def test_decode_rejects_bad_checksum():
    assert decode_feedback(make_feedback(corrupt=True)) is None


def test_parser_resyncs_and_handles_split_reads():
    good1, good2 = make_feedback(sl=1), make_feedback(sl=2)
    stream = b"\x00\x11" + good1 + make_feedback(corrupt=True) + b"\xcd" + good2
    p = FeedbackParser()
    got = []
    for i in range(0, len(stream), 5):           # arrive in 5-byte dribbles
        got += p.feed(stream[i:i + 5])
    assert [f.rpm_left for f in got] == [1, 2]
    assert p.bad_frames >= 1


class FakeSerial:
    def __init__(self, data=b""):
        self.data = bytearray(data)
        self.written = bytearray()
        self.closed = False

    @property
    def in_waiting(self):
        return len(self.data)

    def read(self, n):
        out, self.data = bytes(self.data[:n]), self.data[n:]
        return out

    def write(self, b):
        self.written += b

    def close(self):
        self.closed = True


def test_link_poll_and_stop_on_close():
    ser = FakeSerial(make_feedback(bat=3650) + make_feedback(bat=3640))
    with Hoverboard(serial_port=ser) as hb:
        hb.send(30, 30)
        frames = hb.poll()
        assert [f.battery_v for f in frames] == [36.5, 36.4]
        assert hb.latest.battery_v == 36.4
    # one drive command, then zero commands on close
    sent = [struct.unpack("<HhhH", ser.written[i:i + 8])[1:3]
            for i in range(0, len(ser.written), 8)]
    assert sent[0] == (30, 30)
    assert sent[-1] == (0, 0) and len(sent) >= 2
    assert ser.closed
