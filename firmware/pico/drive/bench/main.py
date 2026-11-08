# firmware/pico/drive/bench/main.py
#
# BENCH-TEST firmware for the Pico 2 drive controller. Copy to the board as
# main.py, together with ../protocol.py. Nothing needs to be wired to GP0/GP1.
#
# It is the same loop as ../main.py (same parser, same pulse mapping, same
# non-blocking read, same failsafe) with one addition: it reports back over
# USB serial, so the host can MEASURE what the outputs are instead of looking
# at an LED. Keep the loop in step with ../main.py when that one changes.
#
# Replies (Pico -> host), one per line:
#   "OK t s esc_ns steer_ns"  after a valid command (pulse widths read back
#                             from the PWM hardware, not computed)
#   "BAD <line>"              after a malformed line (state must not change)
#   "FAILSAFE esc_ns"         the moment the failsafe cuts throttle
#   "STAT t s esc_ns steer_ns age_ms max_gap_ms"   reply to "?"
#       age_ms     = time since the last valid command
#       max_gap_ms = longest gap between loop passes since the last "?"
#                    (shows whether a read ever stalled the loop)
#
# UNTESTED ON HARDWARE beyond the bench: no ESC or servo attached.

import sys
from machine import Pin, PWM
from time import ticks_ms, ticks_diff, sleep_ms

try:
    import uselect as select
except ImportError:
    import select

import protocol

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

poller = select.poll()
poller.register(sys.stdin, select.POLLIN)


def set_outputs(throttle, steer_val):
    esc.duty_ns(protocol.cmd_to_pulse_ns(throttle))
    steer.duty_ns(protocol.cmd_to_pulse_ns(steer_val))


def read_line_nonblocking():
    if poller.poll(0):
        return sys.stdin.readline()
    return None


def report(tag, *fields):
    print(tag, *fields)


throttle = 0
steer_val = 0
set_outputs(throttle, steer_val)

last_cmd = ticks_ms()
last_blink = ticks_ms()
last_pass = ticks_ms()
max_gap = 0
led_state = 0
tripped = False

report("READY")

while True:
    line = read_line_nonblocking()
    if line is not None:
        if line.strip() == "?":
            report("STAT", throttle, steer_val, esc.duty_ns(), steer.duty_ns(),
                   ticks_diff(ticks_ms(), last_cmd), max_gap)
            max_gap = 0
        else:
            parsed = protocol.parse_command(line)
            if parsed is not None:
                throttle, steer_val = parsed
                last_cmd = ticks_ms()
                tripped = False
                set_outputs(throttle, steer_val)
                report("OK", throttle, steer_val, esc.duty_ns(), steer.duty_ns())
            else:
                report("BAD", line.strip())

    if ticks_diff(ticks_ms(), last_cmd) > FAILSAFE_MS:
        throttle = 0
        if not tripped:
            set_outputs(throttle, steer_val)
            report("FAILSAFE", esc.duty_ns())
            tripped = True

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
