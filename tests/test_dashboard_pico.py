"""Dashboard Pico panel (forrest.dashboard.pico): state file -> tiles."""
import json

from forrest.dashboard import pico as dp
from forrest.dashboard.status import GROUPS

NOW = 1_000_000.0
STAT = {"throttle": 0, "steer": 0, "esc_ns": 1499901, "steer_ns": 1499901,
        "age_ms": 244_749, "max_gap_ms": 7, "trips": 1}


def snap(**over):
    s = {"updated": NOW - 0.5, "link": "up", "port": "/dev/ttyACM0", "since": NOW - 60,
         "last_answer_age_s": 0.0, "rtt_ms": 5.1, "failsafe": True, "stat": STAT,
         "polls": 60, "answered": 60,
         "events": [{"t": NOW - 60, "kind": "LINK", "text": "no_device -> up: opened /dev/ttyACM0"}]}
    s.update(over)
    return s


def by_key(p):
    return {t["key"]: t for t in p["tiles"]}


def test_up_shows_four_tiles_in_the_pico_group():
    p = dp.panel(snap(), NOW)
    t = by_key(p)
    assert p["monitor"] == "running"
    assert list(t) == ["pico_link", "pico_drive", "pico_loop", "pico_trips"]
    assert all(x["group"] == "pico" for x in p["tiles"])
    assert "pico" in [g[0] for g in GROUPS]
    assert t["pico_link"]["value"] == "up" and t["pico_link"]["level"] == "ok"
    assert t["pico_link"]["detail"].startswith("round trip 5 ms")
    assert t["pico_drive"]["value"] == "Failsafe"
    assert "ESC 1.500 ms" in t["pico_drive"]["detail"] and "no command for 4 min" in t["pico_drive"]["detail"]
    assert t["pico_loop"]["value"] == "7 ms" and t["pico_loop"]["level"] == "ok"
    assert t["pico_trips"]["value"] == "1"


def test_loop_gap_limits():
    assert by_key(dp.panel(snap(stat={**STAT, "max_gap_ms": 60}), NOW))["pico_loop"]["level"] == "warn"
    assert by_key(dp.panel(snap(stat={**STAT, "max_gap_ms": 200}), NOW))["pico_loop"]["level"] == "bad"


def test_commanded_and_last_trip_time():
    ev = {"t": NOW - 30, "kind": "FAILSAFE", "text": "FAILSAFE 1499901"}
    p = dp.panel(snap(failsafe=False, stat={**STAT, "age_ms": 40, "trips": 2},
                      events=[ev]), NOW)
    t = by_key(p)
    assert t["pico_drive"]["value"] == "Commanded"
    assert "last" in t["pico_trips"]["detail"] and t["pico_trips"]["value"] == "2"


def test_not_connected_is_a_caution_and_hides_the_rest():
    p = dp.panel(snap(link="no_device", port=None, stat=None, failsafe=None), NOW)
    assert [t["key"] for t in p["tiles"]] == ["pico_link"]
    assert p["tiles"][0]["value"] == "not connected" and p["tiles"][0]["level"] == "warn"


def test_silent_pico_is_bad():
    p = dp.panel(snap(link="down", last_answer_age_s=4.2), NOW)
    assert p["tiles"][0]["level"] == "bad" and "4 s" in p["tiles"][0]["detail"]


def test_monitor_stopped_or_missing_is_no_data():
    stale = dp.panel(snap(updated=NOW - 120), NOW)
    assert stale["monitor"] == "stopped"
    assert stale["tiles"][0]["level"] == "na" and "2 min ago" in stale["tiles"][0]["detail"]
    assert stale["events"]                                    # last events still shown
    missing = dp.panel(None, NOW)
    assert missing["tiles"][0]["level"] == "na" and "no state file" in missing["tiles"][0]["detail"]


def test_read_state(tmp_path):
    f = tmp_path / "pico.json"
    assert dp.read_state(f) is None
    f.write_text("{half")
    assert dp.read_state(f) is None
    f.write_text(json.dumps(snap()))
    assert dp.read_state(f)["link"] == "up"
