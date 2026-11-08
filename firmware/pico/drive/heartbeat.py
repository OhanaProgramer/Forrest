# firmware/pico/drive/heartbeat.py
#
# The Pi-is-alive watchdog behind the failsafe. Pure logic: no `machine`, no
# clock reads. The caller passes the time in, so the same code runs on the
# Pico and under the repo's host pytest (tests/test_pico_heartbeat.py).
#
# What it decides: whether the Pi is still in control. Every valid drive
# command "feeds" it. If nothing feeds it for longer than timeout_ms, it trips,
# and main.py must cut throttle. Without it, a crashed Pi or an unplugged cable
# would leave the truck running at its last speed.
#
# What does NOT feed it: status polls ("?") and bad lines. The monitor only
# polls, so a running dashboard can never keep the drive alive.


def _plain_diff(a, b):
    return a - b


class Heartbeat:
    def __init__(self, timeout_ms, now_ms, diff=_plain_diff):
        # diff(a, b) = a - b in ms. On the Pico, pass time.ticks_diff: the ms
        # counter wraps around, and plain subtraction would break at the wrap.
        self.timeout_ms = timeout_ms
        self._diff = diff
        self._last = now_ms
        self.tripped = False
        self.trips = 0          # times it has tripped since boot

    def feed(self, now_ms):
        """A valid command arrived. Returns True if this ends a trip."""
        self._last = now_ms
        if self.tripped:
            self.tripped = False
            return True
        return False

    def age_ms(self, now_ms):
        """Time since the last valid command."""
        return self._diff(now_ms, self._last)

    def check(self, now_ms):
        """Call every loop pass. Returns True only on the pass where it trips,
        so the caller reports the trip once, not every pass."""
        if not self.tripped and self.age_ms(now_ms) > self.timeout_ms:
            self.tripped = True
            self.trips += 1
            return True
        return False
