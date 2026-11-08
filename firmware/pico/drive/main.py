# firmware/pico/drive/main.py
#
# Pico 2 drive controller: the loop that wires the modules together.
# Deploy with firmware/pico/deploy.sh (copies every module, then restarts).
#
#   comm.py       USB serial: complete lines in, reply lines out (non-blocking)
#   heartbeat.py  Pi-is-alive watchdog; trips the failsafe
#   protocol.py   command parsing + command -> pulse width
#   main.py       this file: hardware pins + the loop
#
# Lines from the Pi:
#   "throttle,steer"   e.g. "250,-100", each in [-1000, 1000]. Feeds the heartbeat.
#   "?"                status request. Does NOT feed the heartbeat.
#
# Replies (Pico -> Pi), one per line:
#   "READY"                     after boot
#   "OK t s esc_ns steer_ns"    after a valid command (pulse widths read back
#                               from the PWM hardware, not computed)
#   "BAD <line>"                malformed line; state does not change
#   "FAILSAFE esc_ns"           the moment the heartbeat trips and throttle is cut
#   "STAT t s esc_ns steer_ns age_ms max_gap_ms trips"   reply to "?"
#       age_ms     = time since the last valid command
#       max_gap_ms = longest gap between loop passes since the last "?"
#       trips      = failsafe trips since boot
#
# UNTESTED ON HARDWARE beyond the bench: no ESC or servo attached to GP0/GP1.

from machine import Pin, PWM
from time import ticks_ms, ticks_diff, sleep_ms

import comm
import protocol
from heartbeat import Heartbeat

ESC_PIN = 0
STEER_PIN = 1
SERVO_FREQ = 50
FAILSAFE_MS = 500
BLINK_MS = 250

esc = PWM(Pin(ESC_PIN))
steer = PWM(Pin(STEER_PIN))
esc.freq(SERVO_FREQ)
steer.freq(SERVO_FREQ)

try:
    led = Pin("LED", Pin.OUT)
except (TypeError, ValueError):
    led = Pin(25, Pin.OUT)


def set_outputs(throttle, steer_val):
    esc.duty_ns(protocol.cmd_to_pulse_ns(throttle))
    steer.duty_ns(protocol.cmd_to_pulse_ns(steer_val))


link = comm.Link()
hb = Heartbeat(FAILSAFE_MS, ticks_ms(), diff=ticks_diff)

throttle = 0
steer_val = 0
set_outputs(throttle, steer_val)

last_blink = ticks_ms()
last_pass = ticks_ms()
max_gap = 0
led_state = 0

link.send("READY")

while True:
    for line in link.poll():
        if line.strip() == "?":
            link.send("STAT", throttle, steer_val, esc.duty_ns(), steer.duty_ns(),
                      hb.age_ms(ticks_ms()), max_gap, hb.trips)
            max_gap = 0
            continue
        parsed = protocol.parse_command(line)
        if parsed is None:
            link.send("BAD", line.strip())
            continue
        throttle, steer_val = parsed
        hb.feed(ticks_ms())
        set_outputs(throttle, steer_val)
        link.send("OK", throttle, steer_val, esc.duty_ns(), steer.duty_ns())

    if hb.check(ticks_ms()):
        throttle = 0
        set_outputs(throttle, steer_val)
        link.send("FAILSAFE", esc.duty_ns())
    if hb.tripped:
        throttle = 0     # stays cut until a fresh valid command

    set_outputs(throttle, steer_val)

    now = ticks_ms()
    if ticks_diff(now, last_blink) > BLINK_MS:
        led_state ^= 1
        led.value(led_state)
        last_blink = now

    gap = ticks_diff(now, last_pass)
    if gap > max_gap:
        max_gap = gap
    last_pass = now

    sleep_ms(5)
