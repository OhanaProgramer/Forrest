"""Dashboard sidebar (forrest.dashboard.sidebar)."""
from forrest.dashboard.sidebar import sidebar


def rows(sections, key):
    return {r["label"]: r for r in next(s for s in sections if s["key"] == key)["rows"]}


PICO_UP = {"tiles": [
    {"key": "pico_link", "value": "up", "level": "ok"},
    {"key": "pico_drive", "value": "Failsafe", "level": "ok"}]}


def test_no_sensors_are_placeholders():
    s = sidebar()
    assert [x["key"] for x in s] == ["env", "gps", "robot"]
    env = rows(s, "env")
    assert env["Air temp"]["level"] == "na" and env["Air temp"]["detail"] == "no sensor yet"
    assert rows(s, "gps")["Position"]["detail"] == "no GPS yet"
    robot = rows(s, "robot")
    assert robot["Battery"]["level"] == "na"
    assert robot["Drive Pico"]["detail"] == "monitor not running"


def test_with_readings():
    s = sidebar(env={"temp_c": 18.44, "humidity_pct": 41.2, "pressure_hpa": 1012.6},
                gps={"lat": 33.448377, "lon": -112.074037, "sats": 9, "fix": True,
                     "speed_mps": 2.13, "heading_deg": 4},
                battery_v=11.8, pico=PICO_UP)
    assert rows(s, "env")["Air temp"]["value"] == "18.4 °C"
    gps = rows(s, "gps")
    assert gps["Position"]["value"] == "33.44838, -112.07404"
    assert gps["Speed"]["detail"] == "heading 4°"
    robot = rows(s, "robot")
    assert robot["Battery"]["value"] == "11.80 V"
    assert robot["Drive Pico"]["value"] == "up" and robot["Drive"]["value"] == "failsafe"


def test_gps_without_fix_is_a_caution():
    g = rows(sidebar(gps={"lat": 0, "lon": 0, "sats": 2, "fix": False}), "gps")
    assert g["Position"]["value"] == "no fix" and g["Position"]["level"] == "warn"


def test_sensor_pico_row_when_the_panel_has_it():
    from forrest.dashboard.sidebar import sidebar
    pico = {"tiles": PICO_UP["tiles"] + [{"key": "pico_sensors", "value": "on USB", "level": "ok"}]}
    robot = {r["label"]: r for r in next(s for s in sidebar(pico=pico) if s["key"] == "robot")["rows"]}
    assert robot["Sensor Pico"]["value"] == "on USB"
    assert robot["Drive Pico"]["value"] == "up"
