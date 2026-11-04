"""Camera + Hailo detection loop: the one owner of the camera.

Only one process can hold the camera, so this thread owns it and the Hailo,
runs detection on every frame, and publishes:
  - `latest_jpeg`: a small annotated view frame (for the dashboard stream)
  - `status()`: fps, frame count, current detections, last error

Two streams from one capture: `lores` (640x640, the model's input) for
detection at full rate, and `main` (1280x960; the camera requires main to be
at least as large as lores). For the live view, main is shrunk to `view_size`
and encoded only `view_fps` times a second so the viewer costs little CPU.

Ran on forrest-jr (ov5647 + Hailo-8) 2026-11-04: 29.9 fps at 1280x960 main.
"""

from __future__ import annotations

import threading
import time
from typing import Callable, Optional

from forrest.sensing.detections import Detection, parse_nms

DEFAULT_HEF = "/usr/share/hailo-models/yolov8s_h8.hef"
MAIN_SIZE = (1280, 960)


class VisionLoop(threading.Thread):
    def __init__(self, hef_path: str = DEFAULT_HEF, threshold: float = 0.5,
                 view_size: tuple[int, int] = (640, 480), view_fps: float = 10.0,
                 on_detections: Optional[Callable[[float, list[Detection]], None]] = None,
                 encode_jpeg: bool = True):
        super().__init__(daemon=True, name="vision")
        self.hef_path = hef_path
        self.threshold = threshold
        self.view_size = view_size
        self.view_period = 1.0 / view_fps
        self.on_detections = on_detections
        self.encode_jpeg = encode_jpeg  # False for the desktop window (no web stream)
        self._halt = threading.Event()
        self._lock = threading.Lock()
        self.new_frame = threading.Condition()
        self.latest_jpeg: Optional[bytes] = None
        self.latest_view = None  # annotated BGR array, view_size
        self.jpeg_seq = 0
        self._detections: list[Detection] = []
        self._fps = 0.0
        self._frames = 0
        self._error: Optional[str] = None
        self._t0 = time.time()
        self._running = False

    # -- public -------------------------------------------------------------
    def stop(self) -> None:
        self._halt.set()

    def status(self) -> dict:
        with self._lock:
            return {
                "running": self._running,
                "fps": round(self._fps, 1),
                "frames": self._frames,
                "error": self._error,
                "model": self.hef_path.rsplit("/", 1)[-1],
                "threshold": self.threshold,
                "detections": [d.as_record() for d in self._detections],
            }

    # -- thread -------------------------------------------------------------
    def run(self) -> None:
        try:
            self._loop()
        except Exception as e:  # surface on the dashboard rather than die silently
            with self._lock:
                self._error = f"{type(e).__name__}: {e}"
                self._running = False

    def _loop(self) -> None:
        import cv2
        import simplejpeg
        from picamera2 import Picamera2
        from picamera2.devices import Hailo

        with Hailo(self.hef_path) as hailo:
            mh, mw, _ = hailo.get_input_shape()
            cam = Picamera2()
            cfg = cam.create_video_configuration(
                main={"size": MAIN_SIZE, "format": "XRGB8888"},
                lores={"size": (mw, mh), "format": "RGB888"},
                controls={"FrameRate": 30})
            cam.configure(cfg)
            cam.start()
            with self._lock:
                self._running = True
            try:
                last_view, t_fps, n_fps = 0.0, time.time(), 0
                vw, vh = self.view_size
                while not self._halt.is_set():
                    (view, lores), _meta = cam.capture_arrays(["main", "lores"])
                    dets = parse_nms(hailo.run(lores), self.threshold)
                    now = time.time()
                    n_fps += 1
                    with self._lock:
                        self._frames += 1
                        self._detections = dets
                        if now - t_fps >= 1.0:
                            self._fps = n_fps / (now - t_fps)
                            t_fps, n_fps = now, 0
                    if self.on_detections:
                        self.on_detections(now, dets)
                    if now - last_view >= self.view_period:
                        last_view = now
                        img = cv2.resize(view[:, :, :3], self.view_size, interpolation=cv2.INTER_AREA)
                        for d in dets:
                            p0 = (int(d.x0 * vw), int(d.y0 * vh))
                            p1 = (int(d.x1 * vw), int(d.y1 * vh))
                            cv2.rectangle(img, p0, p1, (0, 255, 0), 2)
                            cv2.putText(img, f"{d.label} {d.score:.0%}", (p0[0] + 4, p0[1] + 18),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 0), 2)
                        jpeg = (simplejpeg.encode_jpeg(img, quality=75, colorspace="BGR")
                                if self.encode_jpeg else None)
                        with self.new_frame:
                            self.latest_view = img
                            self.latest_jpeg = jpeg
                            self.jpeg_seq += 1
                            self.new_frame.notify_all()
            finally:
                cam.stop()
                cam.close()
                with self._lock:
                    self._running = False
