# BME688 driver (temperature, humidity, pressure, gas resistance) for MicroPython.
# Also imports under CPython, so the maths is tested on the host with a fake I2C.
#
# Written from the Bosch BME688 datasheet / BME68x reference API (float maths).
# Forced mode, one heater step: trigger() starts a measurement and returns at once;
# ready() / collect() pick it up later, so a read never blocks the main loop
# (a measurement with the gas heater takes ~200 ms).
#
# Gas: raw resistance in ohms only. Bosch's IAQ / CO2-equivalent scores need
# their closed-source BSEC library; we log the raw value and its trend.
#
# Address 0x77 (Adafruit default; 0x76 with the SDO jumper). Chip id 0x61,
# variant 0x01 = BME688 (0x00 would be a BME680, whose gas registers differ).

try:
    import time
    ticks_ms = time.ticks_ms
    ticks_diff = time.ticks_diff
except AttributeError:          # CPython (tests)
    import time
    def ticks_ms():
        return int(time.monotonic() * 1000)
    def ticks_diff(a, b):
        return a - b

ADDR = 0x77
CHIP_ID = 0x61
VARIANT_BME688 = 0x01

REG_CHIP_ID = 0xD0
REG_VARIANT = 0xF0
REG_RESET = 0xE0
REG_STATUS = 0x1D          # field 0: status, then press/temp/hum/gas
REG_CTRL_GAS_0 = 0x70
REG_CTRL_GAS_1 = 0x71
REG_CTRL_HUM = 0x72
REG_CTRL_MEAS = 0x74
REG_CONFIG = 0x75
REG_RES_HEAT_0 = 0x5A
REG_GAS_WAIT_0 = 0x64

OS_CODE = {0: 0, 1: 1, 2: 2, 4: 3, 8: 4, 16: 5}     # oversampling -> register code
FILTER_CODE = {0: 0, 1: 1, 3: 2, 7: 3, 15: 4, 31: 5, 63: 6, 127: 7}
MODE_SLEEP, MODE_FORCED = 0, 1
NEW_DATA = 0x80
GAS_VALID = 0x20
HEAT_STAB = 0x10
RUN_GAS_BME688 = 0x20      # ctrl_gas_1 bit 5 on the BME688 (bit 4 on the BME680)


def _s8(v):
    return v - 256 if v > 127 else v


def _s16(v):
    return v - 65536 if v > 32767 else v


def parse_calibration(c1, c2, c3):
    """c1 = 23 bytes from 0x8A, c2 = 14 bytes from 0xE1, c3 = 5 bytes from 0x00."""
    c = bytes(c1) + bytes(c2) + bytes(c3)
    u16 = lambda lo: c[lo] | (c[lo + 1] << 8)
    return {
        "t1": u16(31), "t2": _s16(u16(0)), "t3": _s8(c[2]),
        "p1": u16(4), "p2": _s16(u16(6)), "p3": _s8(c[8]), "p4": _s16(u16(10)),
        "p5": _s16(u16(12)), "p6": _s8(c[15]), "p7": _s8(c[14]), "p8": _s16(u16(18)),
        "p9": _s16(u16(20)), "p10": c[22],
        "h1": (c[25] << 4) | (c[24] & 0x0F), "h2": (c[23] << 4) | (c[24] >> 4),
        "h3": _s8(c[26]), "h4": _s8(c[27]), "h5": _s8(c[28]), "h6": c[29], "h7": _s8(c[30]),
        "gh1": _s8(c[35]), "gh2": _s16(u16(33)), "gh3": _s8(c[36]),
        "res_heat_val": _s8(c[37]), "res_heat_range": (c[39] & 0x30) >> 4,
        "range_sw_err": _s8(c[41] & 0xF0) // 16,
    }


def comp_temperature(adc, cal):
    """-> (deg C, t_fine)."""
    var1 = ((adc / 16384.0) - (cal["t1"] / 1024.0)) * cal["t2"]
    var2 = ((adc / 131072.0) - (cal["t1"] / 8192.0)) ** 2 * (cal["t3"] * 16.0)
    t_fine = var1 + var2
    return t_fine / 5120.0, t_fine


def comp_pressure(adc, t_fine, cal):
    """-> Pa."""
    var1 = (t_fine / 2.0) - 64000.0
    var2 = var1 * var1 * (cal["p6"] / 131072.0)
    var2 = var2 + (var1 * cal["p5"] * 2.0)
    var2 = (var2 / 4.0) + (cal["p4"] * 65536.0)
    var1 = (((cal["p3"] * var1 * var1) / 16384.0) + (cal["p2"] * var1)) / 524288.0
    var1 = (1.0 + (var1 / 32768.0)) * cal["p1"]
    p = 1048576.0 - adc
    if var1 == 0:
        return 0.0
    p = ((p - (var2 / 4096.0)) * 6250.0) / var1
    var1 = (cal["p9"] * p * p) / 2147483648.0
    var2 = p * (cal["p8"] / 32768.0)
    var3 = (p / 256.0) ** 3 * (cal["p10"] / 131072.0)
    return p + (var1 + var2 + var3 + (cal["p7"] * 128.0)) / 16.0


def comp_humidity(adc, t_fine, cal):
    """-> % RH, clamped to 0..100."""
    t = t_fine / 5120.0
    var1 = adc - ((cal["h1"] * 16.0) + ((cal["h3"] / 2.0) * t))
    var2 = var1 * ((cal["h2"] / 262144.0) *
                   (1.0 + ((cal["h4"] / 16384.0) * t) + ((cal["h5"] / 1048576.0) * t * t)))
    var3 = cal["h6"] / 16384.0
    var4 = cal["h7"] / 2097152.0
    h = var2 + ((var3 + (var4 * t)) * var2 * var2)
    return min(100.0, max(0.0, h))


def comp_gas_bme688(adc, gas_range):
    """-> ohms (the BME688 / 'high' variant formula)."""
    var1 = 262144 >> gas_range
    var2 = 4096 + (adc - 512) * 3
    return 1000000.0 * var1 / var2


def heater_resistance(target_c, ambient_c, cal):
    """Heater set point (res_heat_0 register value) for a target plate temperature."""
    var1 = (cal["gh1"] / 16.0) + 49.0
    var2 = ((cal["gh2"] / 32768.0) * 0.0005) + 0.00235
    var3 = cal["gh3"] / 1024.0
    var4 = var1 * (1.0 + (var2 * target_c))
    var5 = var4 + (var3 * ambient_c)
    r = 3.4 * ((var5 * (4.0 / (4.0 + cal["res_heat_range"]))
                * (1.0 / (1.0 + (cal["res_heat_val"] * 0.002)))) - 25)
    return max(0, min(255, int(r)))


def heater_duration(ms):
    """gas_wait_0 encoding: 6-bit value x 1/4/16/64; 0xFF = max (~4 s)."""
    if ms >= 0xFC0:
        return 0xFF
    factor = 0
    while ms > 0x3F:
        ms //= 4
        factor += 1
    return ms + factor * 64


def parse_field(buf, cal):
    """17 bytes from 0x1D -> reading dict (None if no new data)."""
    if not buf[0] & NEW_DATA:
        return None
    p_adc = (buf[2] << 12) | (buf[3] << 4) | (buf[4] >> 4)
    t_adc = (buf[5] << 12) | (buf[6] << 4) | (buf[7] >> 4)
    h_adc = (buf[8] << 8) | buf[9]
    g_adc = (buf[15] << 2) | (buf[16] >> 6)      # 0x2C / 0x2D on the BME688
    g_range = buf[16] & 0x0F
    t, t_fine = comp_temperature(t_adc, cal)
    gas_ok = bool(buf[16] & GAS_VALID) and bool(buf[16] & HEAT_STAB)
    return {
        "temp_c": round(t, 2),
        "humidity_pct": round(comp_humidity(h_adc, t_fine, cal), 2),
        "pressure_hpa": round(comp_pressure(p_adc, t_fine, cal) / 100.0, 2),
        "gas_ohm": int(comp_gas_bme688(g_adc, g_range)) if gas_ok else None,
        # ADC pinned at full scale: the real resistance is at or below gas_ohm.
        # Seen on a new sensor before burn-in (2026-11-23: 0xFF 0xFD -> 5684 ohm
        # every reading, until the heater had run hotter / longer).
        "gas_low": gas_ok and g_adc == 1023,
    }


class BME688:
    def __init__(self, i2c, addr=ADDR, heater_c=320, heater_ms=150,
                 os_t=2, os_p=4, os_h=1, filt=3):
        self.i2c, self.addr = i2c, addr
        chip = self._r(REG_CHIP_ID, 1)[0]
        variant = self._r(REG_VARIANT, 1)[0]
        if chip != CHIP_ID:
            raise OSError("BME688: chip id %#x at %#x, want %#x" % (chip, addr, CHIP_ID))
        if variant != VARIANT_BME688:
            raise OSError("BME688: variant %#x (a BME680?), this driver is for 0x01" % variant)
        self._w(REG_RESET, 0xB6)
        time.sleep(0.01)
        self.cal = parse_calibration(self._r(0x8A, 23), self._r(0xE1, 14), self._r(0x00, 5))
        self.heater_c, self.heater_ms = heater_c, heater_ms
        self._ctrl_meas = (OS_CODE[os_t] << 5) | (OS_CODE[os_p] << 2)
        self._w(REG_CTRL_HUM, OS_CODE[os_h])
        self._w(REG_CONFIG, FILTER_CODE[filt] << 2)
        self._w(REG_GAS_WAIT_0, heater_duration(heater_ms))
        self._w(REG_CTRL_GAS_1, RUN_GAS_BME688 | 0)      # heater step 0
        self.ambient_c = 25.0
        self._t0 = None

    def _r(self, reg, n):
        return self.i2c.readfrom_mem(self.addr, reg, n)

    def _w(self, reg, val):
        self.i2c.writeto_mem(self.addr, reg, bytes([val]))

    def trigger(self):
        """Start one forced measurement (returns at once)."""
        self._w(REG_RES_HEAT_0, heater_resistance(self.heater_c, self.ambient_c, self.cal))
        self._w(REG_CTRL_MEAS, self._ctrl_meas | MODE_FORCED)
        self._t0 = ticks_ms()

    def collect(self):
        """The reading if the measurement is done, else None. Never waits."""
        if self._t0 is None:
            return None
        r = parse_field(self._r(REG_STATUS, 17), self.cal)
        if r is not None:
            self._t0 = None
            self.ambient_c = r["temp_c"]       # heater target is set relative to air temp
        return r

    def busy_ms(self):
        """How long the current measurement has been running (None if idle)."""
        return None if self._t0 is None else ticks_diff(ticks_ms(), self._t0)
