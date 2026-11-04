"""Forrest Jr dashboard: a small web server on the Pi.

    /              the dashboard page
    /stream        live annotated view (MJPEG)
    /api/status    hardware status + vision status (JSON)
    /api/history   the last 30 min of samples, as columns (JSON)

Read-only by design: nothing here moves hardware. Bind it to the Tailscale
address so it is reachable from the tailnet only.
"""

from __future__ import annotations

import json
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional

from forrest.dashboard.status import LIMITS, Monitor

PAGE = Path(__file__).with_name("index.html")
BOUNDARY = "forrestframe"


def tailscale_ip() -> Optional[str]:
    try:
        out = subprocess.run(["tailscale", "ip", "-4"], capture_output=True, text=True,
                             timeout=3, check=True).stdout.split()
        return out[0] if out else None
    except (FileNotFoundError, subprocess.SubprocessError):
        return None


def make_handler(vision):
    """`vision` is a VisionLoop, or None to run without a camera (the default)."""
    monitor = Monitor().start()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):  # keep the terminal quiet
            pass

        def _send(self, code: int, body: bytes, ctype: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path = self.path.split("?", 1)[0]
            if path == "/":
                self._send(200, PAGE.read_bytes(), "text/html; charset=utf-8")
            elif path == "/api/status":
                body = {"hardware": monitor.read(), "limits": LIMITS,
                        "vision": vision.status() if vision else {"running": False,
                                                                  "error": "camera off (start with --camera)"}}
                self._send(200, json.dumps(body).encode(), "application/json")
            elif path == "/api/history":
                q = self.path.partition("?")[2]
                since = float(q.split("since=", 1)[1].split("&")[0]) if "since=" in q else None
                self._send(200, json.dumps(monitor.history_columns(since)).encode(),
                           "application/json")
            elif path == "/stream":
                self._stream()
            else:
                self._send(404, b"not found", "text/plain")

        def _stream(self):
            if vision is None:
                self._send(503, b"no camera", "text/plain")
                return
            self.send_response(200)
            self.send_header("Content-Type", f"multipart/x-mixed-replace; boundary={BOUNDARY}")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            seq = 0  # 0 = no frame published yet
            try:
                while True:
                    with vision.new_frame:
                        vision.new_frame.wait_for(lambda: vision.jpeg_seq != seq, timeout=5)
                        if vision.jpeg_seq == seq or vision.latest_jpeg is None:
                            continue
                        seq, jpeg = vision.jpeg_seq, vision.latest_jpeg
                    self.wfile.write(f"--{BOUNDARY}\r\nContent-Type: image/jpeg\r\n"
                                     f"Content-Length: {len(jpeg)}\r\n\r\n".encode())
                    self.wfile.write(jpeg)
                    self.wfile.write(b"\r\n")
            except (BrokenPipeError, ConnectionResetError):
                pass  # viewer closed the page

    return Handler


def serve(host: str, port: int, vision=None) -> ThreadingHTTPServer:
    httpd = ThreadingHTTPServer((host, port), make_handler(vision))
    httpd.daemon_threads = True
    return httpd
