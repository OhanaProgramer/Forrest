# firmware/pico/drive/protocol.py
#
# Pure command + mapping logic for the Jr drive Pico. NO hardware imports here
# (no `machine`), so it runs under the repo's host pytest. The hardware loop
# lives in main.py and imports this.
#
# UNTESTED ON HARDWARE as of 2026-11-05 — written ahead of the RC truck arriving.
# The logic below IS covered by tests/test_pico_protocol.py (host-side).

# Command range the Pi sends, per axis.
CMD_MIN = -1000
CMD_MAX = 1000

# Standard RC servo / ESC pulse widths, in nanoseconds. 1.5 ms = neutral/center.
PULSE_MIN_NS = 1_000_000      # full reverse / full left
PULSE_NEUTRAL_NS = 1_500_000  # stop / center
PULSE_MAX_NS = 2_000_000      # full forward / full right


def clamp(value, lo, hi):
    if value < lo:
        return lo
    if value > hi:
        return hi
    return value


def parse_command(line):
    """Parse one command line from the Pi.

    Format: "throttle,steer" as integers, e.g. "250,-100".
    Returns (throttle, steer) clamped to [CMD_MIN, CMD_MAX], or None if the
    line is malformed. The caller must IGNORE a None (never act on a bad line).
    """
    if not line:
        return None
    parts = line.strip().split(",")
    if len(parts) != 2:
        return None
    try:
        throttle = int(parts[0])
        steer = int(parts[1])
    except ValueError:
        return None
    return (clamp(throttle, CMD_MIN, CMD_MAX), clamp(steer, CMD_MIN, CMD_MAX))


def cmd_to_pulse_ns(value):
    """Map a command value in [-1000, 1000] to a servo pulse width in ns,
    in [1_000_000, 2_000_000], with 0 -> 1_500_000 (neutral)."""
    value = clamp(value, CMD_MIN, CMD_MAX)
    half_span = (PULSE_MAX_NS - PULSE_MIN_NS) // 2  # 500_000 ns each side
    return PULSE_NEUTRAL_NS + (value * half_span) // CMD_MAX
