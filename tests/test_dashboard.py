"""Dashboard: monitor parsers, limits, tiles and server routes, without hardware."""

import json
import threading
import urllib.request

from forrest.dashboard import status as st
from forrest.dashboard.server import serve

PROC_STAT_A = "cpu  100 0 50 800 50 0 0 0 0 0\ncpu0 1 2 3 4\n"
PROC_STAT_B = "cpu  160 0 70 880 70 0 0 0 0 0\ncpu0 1 2 3 4\n"

NET_DEV = """Inter-|   Receive                                                |  Transmit
 face |bytes    packets errs drop fifo frame compressed multicast|bytes    packets errs drop fifo colls carrier compressed
    lo:    1000      10    0    0    0     0          0         0     1000      10    0    0    0     0       0          0
 wlan0: 5000000    4000    0    0    0     0          0         0   200000    1500    0    0    0     0       0          0
"""

WIRELESS = """Inter-| sta-|   Quality        |   Discarded packets               | Missed | WE
 face | tus | link level noise |  nwid  crypt   frag  retry   misc | beacon | 22
 wlan0: 0000   68.  -42.  -256        0      0      0   1218      0        0
"""


def test_cpu_percent_from_two_samples():
    a, b = st.parse_proc_stat(PROC_STAT_A), st.parse_proc_stat(PROC_STAT_B)
    # busy grew 80 (60 user + 20 system), total grew 180 -> 44.4 %
    assert st.cpu_percent(a, b) == 44.4


def test_meminfo_uptime():
    mem = st.parse_meminfo("MemTotal:  8000000 kB\nMemFree: 1 kB\nMemAvailable: 6000000 kB\n")
    assert mem == {"total_mb": 7812, "available_mb": 5859, "used_pct": 25.0}
    assert st.parse_uptime("3061.27 12000.0\n") == 3061.27


def test_network_parsers():
    assert st.parse_net_dev(NET_DEV)["wlan0"] == (5000000, 200000)
    assert st.parse_wireless(WIRELESS) == {"wlan0": -42.0}
    ip = '[{"ifname":"lo","addr_info":[{"local":"127.0.0.1"}]},{"ifname":"wlan0","addr_info":[{"local":"192.168.0.162"}]},{"ifname":"eth0","addr_info":[]}]'
    assert st.parse_ip_json(ip) == {"lo": "127.0.0.1", "wlan0": "192.168.0.162"}
    assert st.parse_pmic_volt("     EXT5V_V volt(24)=5.15498000V\n") == 5.155
    assert st.parse_pmic_volt("") is None


def test_levels_high_and_low():
    assert st.level("cpu_temp", 60) == "ok"
    assert st.level("cpu_temp", 70) == "warn"
    assert st.level("cpu_temp", 82) == "bad"
    assert st.level("wifi_dbm", -42) == "ok"      # smaller (more negative) is worse
    assert st.level("wifi_dbm", -75) == "warn"
    assert st.level("wifi_dbm", -85) == "bad"
    assert st.level("input_v", None) == "na"
    assert st.worst("ok", "warn", "na") == "warn"
    assert st.worst("na") == "na"


def test_human_formats():
    assert st.human_rate(512) == "512 B/s"
    assert st.human_rate(12_300) == "12.3 KB/s"
    assert st.human_rate(None) == "–"
    assert st.human_duration(125) == "2 min"
    assert st.human_duration(3 * 3600 + 120) == "3 h 2 m"
    assert st.human_duration(2 * 86400 + 5 * 3600) == "2 d 5 h"


def _raw(**over):
    raw = {
        "cpu": {"pct": 12.0, "temp_c": 58.0, "ghz": 2.4, "max_ghz": 2.4},
        "hailo_temp_c": 46.0,
        "power": {"throttled": "0x0", "ok": True, "problems": [], "input_v": 5.15},
        "fan_rpm": 4000,
        "memory": {"total_mb": 8000, "available_mb": 6000, "used_pct": 25.0},
        "disk": {"total_gb": 30.8, "free_gb": 19.2, "used_pct": 33.3},
        "network": {"wlan0": {"ip": "192.168.0.162", "signal_dbm": -42.0,
                              "rx_bps": 1500.0, "tx_bps": 300.0}},
        "tailscale": {"state": "Running", "ip": "100.123.84.14", "host": "forrest-jr"},
        "uptime_s": 4000.0,
    }
    raw.update(over)
    return raw


def test_tiles_all_good():
    tiles = {t["key"]: t for t in st.tiles(_raw())}
    assert list(tiles) == ["cpu_temp", "hailo", "fan", "power", "cpu", "mem", "disk",
                           "uptime", "wlan0", "tailscale"]
    assert [tiles[k]["group"] for k in tiles] == ["thermal"] * 3 + ["power"] + ["system"] * 4 + ["network"] * 2
    assert all(t["level"] == "ok" for t in tiles.values())
    assert tiles["cpu"]["detail"] == "2.40 of 2.40 GHz"
    assert tiles["cpu_temp"]["detail"] == "22.0 °C below throttle"
    assert tiles["power"]["value"] == "all clear"
    assert tiles["power"]["detail"] == "input 5.15 V"
    assert tiles["wlan0"]["title"] == "Wi-Fi"
    assert tiles["tailscale"]["value"] == "up"


def test_tiles_flag_problems():
    raw = _raw(cpu={"pct": 50.0, "temp_c": 81.0, "ghz": 1.5, "max_ghz": 2.4},
               power={"throttled": "0x50000", "ok": False, "input_v": 4.9,
                      "problems": ["under-voltage has occurred", "throttling has occurred"]},
               tailscale=None, hailo_temp_c=None)
    tiles = {t["key"]: t for t in st.tiles(raw)}
    assert tiles["cpu"]["level"] == "ok"             # load is fine...
    assert tiles["cpu_temp"]["level"] == "bad"       # ...but it is hot
    assert tiles["cpu_temp"]["detail"] == "at throttle limit"
    assert tiles["power"]["value"] == "seen since boot"
    assert tiles["power"]["level"] == "warn"
    assert tiles["hailo"]["level"] == "na"
    assert tiles["tailscale"]["level"] == "na"


def test_sample_row_from_raw():
    row = st.sample({**_raw(), "time": 100.04})
    assert row == {"t": 100.0, "cpu_pct": 12.0, "cpu_temp": 58.0, "hailo_temp": 46.0,
                   "input_v": 5.15, "fan_rpm": 4000, "mem_pct": 25.0, "wifi_dbm": -42.0,
                   "rx_bps": 1500.0, "tx_bps": 300.0}
    empty = st.sample({**_raw(network={}, memory=None), "time": 1})
    assert empty["wifi_dbm"] is None and empty["rx_bps"] is None and empty["mem_pct"] is None


def test_server_routes_without_camera():
    httpd = serve("127.0.0.1", 0, vision=None)
    port = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        base = f"http://127.0.0.1:{port}"
        page = urllib.request.urlopen(base + "/").read().decode()
        assert "Forrest Jr" in page
        s = json.loads(urllib.request.urlopen(base + "/api/status").read())
        assert s["vision"]["running"] is False
        assert {"tiles", "raw", "time"} <= set(s["hardware"])
        assert "cpu_temp" in s["limits"]
        h = json.loads(urllib.request.urlopen(base + "/api/history").read())
        assert h["every_s"] == 2.0 and len(h["t"]) == len(h["cpu_temp"]) >= 1
        try:
            urllib.request.urlopen(base + "/stream")
            assert False, "stream should be 503 without a camera"
        except urllib.error.HTTPError as e:
            assert e.code == 503
    finally:
        httpd.shutdown()
        httpd.server_close()
