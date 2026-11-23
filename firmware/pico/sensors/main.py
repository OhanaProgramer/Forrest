# Sensor Pico W firmware: BME688 (air) + LIS3DH (motion) on I2C0 (GP4 SDA, GP5 SCL).
#
# Sends JSON lines over USB serial; the Pi's `forrest sensors monitor` reads them.
# Push, not request/response: the Pi only listens, so nothing on the Pi side can
# stall this loop, and a missing Pi costs nothing.
#
#   {"k":"READY", "fw":..., "ms":...}                          at boot
#   {"k":"ENV", "t":C, "rh":%, "p":hPa, "gas":ohm|null, "gas_low":bool, "n":..}  every ENV_MS
#   {"k":"ACC", "x":g, "y":g, "z":g, "tilt":deg, "face":..., "peak":g, "down":bool}  every ACC_MS
#   {"k":"EVT", "what":"FLIP"|"UPRIGHT"|"IMPACT", "v":...}     the moment it happens
#   {"k":"ENV"|"ACC", "err":"..."}                             sensor missing / I2C error
#
# A sensor that's missing or stops answering is reported and retried every
# RETRY_MS; the other one keeps running. Nothing here blocks for long: the
# BME688 is triggered, then collected on a later pass (~200 ms with the heater).
# Onboard LED: short flash every second = loop alive.

import json
import time
from machine import I2C, Pin

import bme688
import lis3dh

FW = "sensors 1 (bme688 + lis3dh)"
ENV_MS = 5000         # heater on ~150 ms per read: ~3 % duty, no self-heating (12-23 test: 85 % duty -> +5 C)
ACC_MS = 1000         # summary line; flips and impacts are sent at once
SAMPLE_MS = 20        # 50 Hz motion sampling
RETRY_MS = 10000

led = Pin("LED", Pin.OUT)
i2c = I2C(0, sda=Pin(4), scl=Pin(5), freq=400000)


def ms():
    return time.ticks_ms()


def since(t):
    return time.ticks_diff(ms(), t)


def send(d):
    d["ms"] = ms()
    print(json.dumps(d))


def try_open(cls, kind):
    try:
        return cls(i2c)
    except OSError as e:
        send({"k": kind, "err": "no sensor: %s" % e})
        return None


send({"k": "READY", "fw": FW})
env = try_open(bme688.BME688, "ENV")
acc = try_open(lis3dh.LIS3DH, "ACC")
motion = lis3dh.Motion()
t_env = t_acc = t_led = t_env_retry = t_acc_retry = ms()
env_busy = False
n_env = 0
last = None

while True:
    # --- motion, every pass ---
    if acc is not None:
        try:
            x, y, z = acc.read()
            last = (x, y, z)
            for what, v in motion.update(x, y, z, ms()):
                send({"k": "EVT", "what": what, "v": v})
        except OSError as e:
            send({"k": "ACC", "err": "read failed: %s" % e})
            acc, t_acc_retry = None, ms()
    elif since(t_acc_retry) >= RETRY_MS:
        t_acc_retry = ms()
        acc = try_open(lis3dh.LIS3DH, "ACC")

    if since(t_acc) >= ACC_MS:
        t_acc = ms()
        if acc is not None and last is not None:
            x, y, z = last
            send({"k": "ACC", "x": round(x, 3), "y": round(y, 3), "z": round(z, 3),
                  "tilt": round(lis3dh.tilt_deg(x, y, z)), "face": lis3dh.face(x, y, z),
                  "peak": motion.take_peak(), "down": motion.upside_down})

    # --- air, trigger then collect ---
    if env is not None:
        try:
            if not env_busy and since(t_env) >= ENV_MS:
                t_env = ms()
                env.trigger()
                env_busy = True
            elif env_busy:
                r = env.collect()
                if r is not None:
                    env_busy = False
                    n_env += 1
                    send({"k": "ENV", "t": r["temp_c"], "rh": r["humidity_pct"], "p": r["pressure_hpa"],
                          "gas": r["gas_ohm"], "gas_low": r["gas_low"], "n": n_env})
                elif env.busy_ms() > 2000:
                    raise OSError("measurement never finished")
        except OSError as e:
            send({"k": "ENV", "err": "read failed: %s" % e})
            env, env_busy, t_env_retry = None, False, ms()
    elif since(t_env_retry) >= RETRY_MS:
        t_env_retry = ms()
        env = try_open(bme688.BME688, "ENV")

    # --- alive LED ---
    led.value(since(t_led) % 1000 < 60)
    if since(t_led) >= 1000:
        t_led = ms()

    time.sleep_ms(SAMPLE_MS)
