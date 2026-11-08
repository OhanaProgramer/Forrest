"""Host tests for the Pico heartbeat (firmware/pico/drive/heartbeat.py)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "firmware/pico/drive"))
from heartbeat import Heartbeat  # noqa: E402


def test_fresh_heartbeat_is_not_tripped():
    hb = Heartbeat(500, now_ms=0)
    assert not hb.tripped
    assert hb.check(500) is False      # exactly at the limit is still alive
    assert hb.age_ms(500) == 500


def test_trips_once_after_timeout():
    hb = Heartbeat(500, now_ms=0)
    assert hb.check(501) is True       # the trip pass
    assert hb.tripped
    assert hb.check(600) is False      # reported once, not every pass
    assert hb.check(5000) is False
    assert hb.trips == 1


def test_feed_keeps_it_alive():
    hb = Heartbeat(500, now_ms=0)
    for t in range(0, 5000, 100):      # a command every 100 ms
        hb.feed(t)
        assert hb.check(t + 50) is False
    assert hb.trips == 0


def test_feed_after_trip_restores_and_can_trip_again():
    hb = Heartbeat(500, now_ms=0)
    hb.check(600)
    assert hb.feed(700) is True        # this feed ended the trip
    assert not hb.tripped
    assert hb.feed(750) is False       # an ordinary feed
    assert hb.check(1300) is True      # 550 ms after the last feed
    assert hb.trips == 2


def test_uses_wrap_safe_diff():
    # The Pico's ms counter wraps; main.py passes time.ticks_diff. Fake a wrap
    # with a 1000-tick counter: 990 -> 10 is 20 ms later, not -980.
    wrap = lambda a, b: ((a - b + 500) % 1000) - 500
    hb = Heartbeat(100, now_ms=990, diff=wrap)
    assert hb.age_ms(10) == 20
    assert hb.check(10) is False
    assert hb.check(95) is True        # 105 ms after 990
