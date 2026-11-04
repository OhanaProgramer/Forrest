"""Dashboard status parsers and server routes, without a camera."""

import json
import threading
import urllib.request

from forrest.dashboard.server import serve
from forrest.dashboard.status import parse_loadavg, parse_meminfo, parse_uptime


def test_parsers():
    assert parse_loadavg("0.52 0.40 0.31 1/234 5678\n") == [0.52, 0.40, 0.31]
    mem = parse_meminfo("MemTotal:  8000000 kB\nMemFree: 1 kB\nMemAvailable: 6000000 kB\n")
    assert mem == {"total_mb": 7812, "available_mb": 5859, "used_pct": 25.0}
    assert parse_uptime("3061.27 12000.0\n") == 3061.27


def test_server_routes_without_camera():
    httpd = serve("127.0.0.1", 0, vision=None)
    port = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        base = f"http://127.0.0.1:{port}"
        page = urllib.request.urlopen(base + "/").read().decode()
        assert "Forrest Jr" in page
        st = json.loads(urllib.request.urlopen(base + "/api/status").read())
        assert st["vision"]["running"] is False
        assert "disk" in st["hardware"]
        try:
            urllib.request.urlopen(base + "/stream")
            assert False, "stream should be 503 without a camera"
        except urllib.error.HTTPError as e:
            assert e.code == 503
    finally:
        httpd.shutdown()
        httpd.server_close()
