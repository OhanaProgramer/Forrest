# LIS3DH accelerometer driver + motion logic for MicroPython (also imports under
# CPython so the logic is tested on the host).
#
# Range +-8 g, high-resolution mode (12-bit, 4 mg per digit), 100 Hz. +-8 g, not
# +-2 g: an impact has to read above 2 g to be seen at all (+-2 g clips at 2 g).
# Address 0x18 (Adafruit default; 0x19 with the SDO jumper). WHO_AM_I = 0x33.
# Verified on Jr 2026-11-23: flat = +1.00 g on Z, upside down = -0.9 g, both Y
# edges and both X sides seen; noise about +-0.01 g.

import math
import struct

ADDR = 0x18
WHO_AM_I = 0x33
REG_WHO_AM_I = 0x0F
REG_CTRL1 = 0x20
REG_CTRL4 = 0x23
REG_OUT_X_L = 0x28
AUTO_INC = 0x80
CTRL1_100HZ_XYZ = 0x57     # ODR 100 Hz, normal mode, X/Y/Z on
CTRL4_8G_HR = 0xA8         # block data update, +-8 g, high resolution
MG_PER_DIGIT = 4           # +-8 g high-res


def raw_to_g(buf):
    """6 bytes from OUT_X_L (little endian, 12-bit left-justified) -> (x, y, z) in g."""
    x, y, z = struct.unpack("<hhh", bytes(buf))
    return tuple((v >> 4) * MG_PER_DIGIT / 1000.0 for v in (x, y, z))


def magnitude(x, y, z):
    return math.sqrt(x * x + y * y + z * z)


def tilt_deg(x, y, z):
    """Angle between the board's Z axis and 'up', 0 = flat face up, 180 = upside down."""
    g = magnitude(x, y, z)
    if g == 0:
        return 0.0
    return math.degrees(math.acos(max(-1.0, min(1.0, z / g))))


def face(x, y, z, min_g=0.8):
    """Which way the board rests: up / down / side+x / side-x / edge+y / edge-y,
    or 'moving' when no axis holds most of gravity."""
    ax, v = max((("x", x), ("y", y), ("z", z)), key=lambda a: abs(a[1]))
    if abs(v) < min_g:
        return "moving"
    if ax == "z":
        return "up" if v > 0 else "down"
    return ("side" if ax == "x" else "edge") + ("+" if v > 0 else "-") + ax


class Motion:
    """Flip and impact detection from a stream of samples (pure; times in ms).

    upside down: Z below -FLIP_Z for FLIP_HOLD_MS (a bump that flicks Z for one
    sample isn't a flip); back upright: Z above +FLIP_Z for FLIP_HOLD_MS.
    impact: |g| at or above IMPACT_G, then IMPACT_GAP_MS quiet before the next.
    Thresholds are bench guesses; set them on the car.
    """
    FLIP_Z = 0.5
    FLIP_HOLD_MS = 500
    IMPACT_G = 2.5
    IMPACT_GAP_MS = 500

    def __init__(self):
        self.upside_down = False
        self._cand_since = None
        self._last_impact = None
        self.peak_g = 0.0                 # since the last take_peak()

    def update(self, x, y, z, now_ms):
        """-> list of events: ("FLIP", z), ("UPRIGHT", z), ("IMPACT", g)."""
        ev = []
        g = magnitude(x, y, z)
        self.peak_g = max(self.peak_g, g)
        if g >= self.IMPACT_G and (self._last_impact is None
                                   or now_ms - self._last_impact >= self.IMPACT_GAP_MS):
            self._last_impact = now_ms
            ev.append(("IMPACT", round(g, 2)))
        flipping = (z < -self.FLIP_Z) if not self.upside_down else (z > self.FLIP_Z)
        if flipping:
            if self._cand_since is None:
                self._cand_since = now_ms
            elif now_ms - self._cand_since >= self.FLIP_HOLD_MS:
                self.upside_down = not self.upside_down
                self._cand_since = None
                ev.append(("FLIP" if self.upside_down else "UPRIGHT", round(z, 2)))
        else:
            self._cand_since = None
        return ev

    def take_peak(self):
        p, self.peak_g = self.peak_g, 0.0
        return round(p, 2)


class LIS3DH:
    def __init__(self, i2c, addr=ADDR):
        self.i2c, self.addr = i2c, addr
        who = i2c.readfrom_mem(addr, REG_WHO_AM_I, 1)[0]
        if who != WHO_AM_I:
            raise OSError("LIS3DH: WHO_AM_I %#x at %#x, want %#x" % (who, addr, WHO_AM_I))
        i2c.writeto_mem(addr, REG_CTRL1, bytes([CTRL1_100HZ_XYZ]))
        i2c.writeto_mem(addr, REG_CTRL4, bytes([CTRL4_8G_HR]))

    def read(self):
        """-> (x, y, z) in g."""
        return raw_to_g(self.i2c.readfrom_mem(self.addr, REG_OUT_X_L | AUTO_INC, 6))
