"""Hardware monitor for the dashboard strip.

Everything is read from files Linux already exposes (/proc, /sys) or from
vcgencmd and tailscale, so no sudo is needed. Parsers are pure functions and
are tested without a Pi; `Monitor.read()` does the reading and keeps the
previous counters so it can turn totals into rates (CPU %, network KB/s).

Limits for green / amber / red live in LIMITS, the one place they are set.
"""

from __future__ import annotations

import json
import platform
import re
import socket
from collections import deque
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Callable, Optional

from forrest.health.pi_power import read_temp_c, read_throttled

# name: (amber at, red at, "high" if bigger is worse / "low" if smaller is worse)
LIMITS = {
    "cpu_pct":    (80, 95, "high"),
    "cpu_temp":   (70, 80, "high"),    # Pi 5 starts throttling at 80 C
    "hailo_temp": (70, 85, "high"),
    "mem_pct":    (80, 90, "high"),
    "disk_pct":   (80, 90, "high"),
    "wifi_dbm":   (-70, -80, "low"),   # -50 excellent, -70 fair, -80 poor
    "input_v":    (5.0, 4.8, "low"),   # Pi 5 wants 5.1 V
}
LEVELS = ["ok", "warn", "bad"]


def level(name: str, value: Optional[float]) -> str:
    if value is None:
        return "na"
    amber, red, worse = LIMITS[name]
    if worse == "high":
        return "bad" if value >= red else "warn" if value >= amber else "ok"
    return "bad" if value <= red else "warn" if value <= amber else "ok"


def worst(*levels: str) -> str:
    known = [l for l in levels if l in LEVELS]
    return max(known, key=LEVELS.index) if known else "na"


# -- parsers (pure) ----------------------------------------------------------

def parse_proc_stat(text: str) -> tuple[int, int]:
    """First 'cpu' line of /proc/stat -> (busy jiffies, total jiffies)."""
    vals = [int(v) for v in text.splitlines()[0].split()[1:]]
    idle = vals[3] + (vals[4] if len(vals) > 4 else 0)  # idle + iowait
    total = sum(vals[:8])  # guest time is already inside user/nice
    return total - idle, total


def cpu_percent(prev: tuple[int, int], cur: tuple[int, int]) -> Optional[float]:
    busy, total = cur[0] - prev[0], cur[1] - prev[1]
    return round(100 * busy / total, 1) if total > 0 else None


def parse_meminfo(text: str) -> dict:
    """'/proc/meminfo' -> {'total_mb', 'available_mb', 'used_pct'}."""
    kb = {}
    for line in text.splitlines():
        key, _, rest = line.partition(":")
        if rest.strip():
            kb[key] = int(rest.split()[0])
    total, avail = kb["MemTotal"], kb["MemAvailable"]
    return {"total_mb": total // 1024, "available_mb": avail // 1024,
            "used_pct": round(100 * (total - avail) / total, 1)}


def parse_uptime(text: str) -> float:
    return float(text.split()[0])


def parse_net_dev(text: str) -> dict[str, tuple[int, int]]:
    """/proc/net/dev -> {iface: (rx bytes, tx bytes)}."""
    out = {}
    for line in text.splitlines()[2:]:
        name, _, rest = line.partition(":")
        f = rest.split()
        if len(f) >= 9:
            out[name.strip()] = (int(f[0]), int(f[8]))
    return out


def parse_wireless(text: str) -> dict[str, float]:
    """/proc/net/wireless -> {iface: signal level in dBm}."""
    out = {}
    for line in text.splitlines()[2:]:
        name, _, rest = line.partition(":")
        f = rest.split()
        if len(f) >= 3:
            out[name.strip()] = float(f[2].rstrip("."))
    return out


def parse_pmic_volt(text: str) -> Optional[float]:
    """'EXT5V_V volt(24)=5.15498000V' -> 5.155."""
    m = re.search(r"=([0-9.]+)V", text)
    return round(float(m.group(1)), 3) if m else None


def parse_ip_json(text: str) -> dict[str, str]:
    """`ip -j -4 addr` -> {iface: first IPv4 address}."""
    return {i["ifname"]: i["addr_info"][0]["local"]
            for i in json.loads(text) if i.get("addr_info")}


def human_rate(bytes_per_s: Optional[float]) -> str:
    if bytes_per_s is None:
        return "–"
    for unit, size in (("MB/s", 1e6), ("KB/s", 1e3)):
        if bytes_per_s >= size:
            return f"{bytes_per_s / size:.1f} {unit}"
    return f"{bytes_per_s:.0f} B/s"


def human_duration(seconds: float) -> str:
    d, rem = divmod(int(seconds), 86400)
    h, rem = divmod(rem, 3600)
    m = rem // 60
    return f"{d} d {h} h" if d else f"{h} h {m} m" if h else f"{m} min"


# -- readers -----------------------------------------------------------------

def _read(path: str) -> Optional[str]:
    try:
        return Path(path).read_text()
    except OSError:
        return None


def _run(*cmd: str, timeout: float = 3) -> Optional[str]:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                              check=True).stdout
    except (FileNotFoundError, subprocess.SubprocessError):
        return None


def _hwmon(name: str, file: str) -> Optional[str]:
    for d in Path("/sys/class/hwmon").glob("hwmon*"):
        if _read(str(d / "name")) and _read(str(d / "name")).strip() == name:
            return _read(str(d / file))
    return None


def read_hailo_temp() -> Optional[float]:
    """Hailo-8 on-chip temperature (about 0.2 s to read). Works while the
    camera loop is using the chip."""
    try:
        from hailo_platform import Device
        dev = Device()
        try:
            t = dev.control.get_chip_temperature()
            return round(max(t.ts0_temperature, t.ts1_temperature), 1)
        finally:
            dev.release()
    except Exception:
        return None


def read_tailscale() -> Optional[dict]:
    out = _run("tailscale", "status", "--json")
    if not out:
        return None
    d = json.loads(out)
    ips = d.get("Self", {}).get("TailscaleIPs") or []
    return {"state": d.get("BackendState"), "ip": next((i for i in ips if "." in i), None),
            "host": d.get("Self", {}).get("HostName")}


class _Cached:
    """Call a slow reader at most once every `every` seconds."""

    def __init__(self, fn: Callable, every: float):
        self.fn, self.every, self.t, self.value = fn, every, 0.0, None

    def get(self):
        if time.time() - self.t >= self.every:
            self.value, self.t = self.fn(), time.time()
        return self.value


# what the history keeps per sample (compact; the charts and sparklines use it)
SERIES = ("cpu_pct", "cpu_temp", "hailo_temp", "input_v", "fan_rpm", "mem_pct",
          "wifi_dbm", "rx_bps", "tx_bps")


def sample(raw: dict) -> dict:
    """One reading -> one history row (None where a value is missing)."""
    nets = raw["network"].values()
    def total(key):
        vals = [n[key] for n in nets if n[key] is not None]
        return round(sum(vals), 1) if vals else None
    wifi = [n["signal_dbm"] for n in nets if n["signal_dbm"] is not None]
    return {
        "t": round(raw["time"], 1),
        "cpu_pct": raw["cpu"]["pct"],
        "cpu_temp": raw["cpu"]["temp_c"],
        "hailo_temp": raw["hailo_temp_c"],
        "input_v": raw["power"]["input_v"],
        "fan_rpm": raw["fan_rpm"],
        "mem_pct": raw["memory"]["used_pct"] if raw["memory"] else None,
        "wifi_dbm": wifi[0] if wifi else None,
        "rx_bps": total("rx_bps"),
        "tx_bps": total("tx_bps"),
    }


class Monitor:
    """Samples hardware every `every` seconds in a background thread and keeps
    `history_s` seconds of history, so trends exist as soon as a page opens.
    Cost on forrest-jr: about half a percent of one core."""

    PHYSICAL = ("wlan0", "eth0")

    def __init__(self, disk_path: str = "/", every: float = 2.0, history_s: float = 1800):
        self.disk_path = disk_path
        self.every = every
        self.history: deque = deque(maxlen=int(history_s / every))
        self._latest: Optional[dict] = None
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._prev_cpu: Optional[tuple[int, int]] = None
        self._prev_net: Optional[tuple[float, dict]] = None
        self._hailo = _Cached(read_hailo_temp, 10)
        self._tailscale = _Cached(read_tailscale, 10)
        self._host = {"name": socket.gethostname(),
                      "model": (_read("/proc/device-tree/model") or "").strip("\x00\n ") or None,
                      "kernel": platform.release()}
        self._volt = _Cached(lambda: parse_pmic_volt(_run("vcgencmd", "pmic_read_adc", "EXT5V_V") or ""), 5)

    def start(self) -> "Monitor":
        if self._thread is None:
            self._thread = threading.Thread(target=self._run, daemon=True, name="monitor")
            self._thread.start()
        return self

    def _run(self) -> None:
        nxt = time.time()
        while True:
            self._sample_once()
            nxt += self.every
            time.sleep(max(0.0, nxt - time.time()))

    def _sample_once(self) -> dict:
        r = self._read()
        with self._lock:
            self._latest = r
            self.history.append(sample(r["raw"]))
        return r

    def read(self) -> dict:
        """The latest reading (taken now if the sampler hasn't run yet)."""
        with self._lock:
            latest = self._latest
        return latest if latest is not None else self._sample_once()

    def history_columns(self, since: Optional[float] = None) -> dict:
        """History as columns: {'t': [...], 'cpu_temp': [...], ...}; only rows
        newer than `since` when given (the page fetches the full window once,
        then just the new rows)."""
        with self._lock:
            rows = [r for r in self.history if since is None or r["t"] > since]
        return {"every_s": self.every, "window_s": self.history.maxlen * self.every,
                **{k: [r[k] for r in rows] for k in ("t",) + SERIES}}

    def _read(self) -> dict:
        now = time.time()
        raw: dict = {"time": now}

        stat = _read("/proc/stat")
        cpu_pct = None
        if stat:
            cur = parse_proc_stat(stat)
            if self._prev_cpu:
                cpu_pct = cpu_percent(self._prev_cpu, cur)
            self._prev_cpu = cur
        freq = _read("/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq")
        fmax = _read("/sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq")
        raw["cpu"] = {"pct": cpu_pct, "temp_c": read_temp_c(),
                      "ghz": round(int(freq) / 1e6, 2) if freq else None,
                      "max_ghz": round(int(fmax) / 1e6, 2) if fmax else None}

        raw["hailo_temp_c"] = self._hailo.get()

        t = read_throttled()
        raw["power"] = {"throttled": None if t is None else hex(t.raw),
                        "ok": None if t is None else t.ok,
                        "problems": [] if t is None else t.problems,
                        "input_v": self._volt.get()}

        fan = _hwmon("pwmfan", "fan1_input")
        raw["fan_rpm"] = int(fan) if fan else None

        mem = _read("/proc/meminfo")
        raw["memory"] = parse_meminfo(mem) if mem else None

        du = shutil.disk_usage(self.disk_path)
        raw["disk"] = {"total_gb": round(du.total / 1e9, 1), "free_gb": round(du.free / 1e9, 1),
                       "used_pct": round(100 * du.used / du.total, 1)}

        ips = parse_ip_json(_run("ip", "-j", "-4", "addr") or "[]")
        wifi = parse_wireless(_read("/proc/net/wireless") or "")
        net = parse_net_dev(_read("/proc/net/dev") or "")
        rates = {}
        if self._prev_net:
            t0, prev = self._prev_net
            dt = now - t0
            for name, (rx, tx) in net.items():
                if name in prev and dt > 0:
                    rates[name] = ((rx - prev[name][0]) / dt, (tx - prev[name][1]) / dt)
        self._prev_net = (now, net)
        raw["network"] = {name: {"ip": ips.get(name), "signal_dbm": wifi.get(name),
                                 "rx_bps": rates.get(name, (None, None))[0],
                                 "tx_bps": rates.get(name, (None, None))[1]}
                          for name in self.PHYSICAL if name in net and ips.get(name)}
        raw["tailscale"] = self._tailscale.get()

        up = _read("/proc/uptime")
        raw["uptime_s"] = parse_uptime(up) if up else None
        raw["host"] = self._host
        return {"time": now, "tiles": tiles(raw), "raw": raw}


# -- presentation (pure, tested) ---------------------------------------------

def tiles(raw: dict) -> list[dict]:
    """Raw readings -> the strip: title, main value, detail line, level."""
    def tile(key, title, value, detail, lvl):
        return {"key": key, "title": title, "value": value, "detail": detail, "level": lvl}

    out = []
    c = raw["cpu"]
    out.append(tile("cpu", "CPU load",
                    f"{c['pct']:.0f}%" if c["pct"] is not None else "–",
                    (f"{c['ghz']:.2f} of {c['max_ghz']:.2f} GHz" if c["ghz"] and c["max_ghz"] else ""),
                    level("cpu_pct", c["pct"])))
    ct = c["temp_c"]
    throttle_at = LIMITS["cpu_temp"][1]
    out.append(tile("cpu_temp", "CPU temp", f"{ct:.1f} °C" if ct is not None else "–",
                    (f"{throttle_at - ct:.1f} °C below throttle" if ct is not None and ct < throttle_at
                     else "at throttle limit" if ct is not None else ""),
                    level("cpu_temp", ct)))

    h = raw["hailo_temp_c"]
    out.append(tile("hailo", "AI HAT", f"{h:.1f} °C" if h is not None else "–",
                    "Hailo-8 chip", level("hailo_temp", h)))

    p = raw["power"]
    v = p["input_v"]
    if p["ok"] is None:
        pv, plvl = "–", "na"
    elif p["ok"]:
        pv, plvl = "all clear", "ok"
    else:
        now_bad = any("now" in x for x in p["problems"])
        pv, plvl = ("problem now" if now_bad else "seen since boot"), ("bad" if now_bad else "warn")
    out.append(tile("power", "Power", pv,
                    "; ".join(p["problems"]) or (f"input {v:.2f} V" if v else ""),
                    worst(plvl, level("input_v", v))))

    f = raw["fan_rpm"]
    out.append(tile("fan", "Fan", f"{f:,} rpm" if f is not None else "–",
                    "Active Cooler" if f else "stopped or not fitted", "ok" if f is not None else "na"))

    m = raw["memory"]
    out.append(tile("mem", "Memory", f"{m['used_pct']:.0f}%" if m else "–",
                    f"{m['available_mb']:,} MB free" if m else "",
                    level("mem_pct", m["used_pct"] if m else None)))

    d = raw["disk"]
    out.append(tile("disk", "Disk free", f"{d['free_gb']} GB",
                    f"{d['used_pct']:.0f}% of {d['total_gb']} GB used", level("disk_pct", d["used_pct"])))

    for name, n in raw["network"].items():
        label = "Wi-Fi" if name.startswith("wl") else "Ethernet"
        sig = n["signal_dbm"]
        value = f"{sig:.0f} dBm" if sig is not None else "connected"
        detail = n["ip"] or ""  # rates live in the network chart and the table
        out.append(tile(name, label, value, detail,
                        level("wifi_dbm", sig) if sig is not None else "ok"))

    ts = raw["tailscale"]
    if ts is None:
        out.append(tile("tailscale", "Tailscale", "–", "not found", "na"))
    else:
        up = ts["state"] == "Running"
        out.append(tile("tailscale", "Tailscale", "up" if up else (ts["state"] or "down").lower(),
                        ts["ip"] or "", "ok" if up else "bad"))

    u = raw["uptime_s"]
    out.append(tile("uptime", "Uptime", human_duration(u) if u is not None else "–", "since boot", "ok"))
    return out
