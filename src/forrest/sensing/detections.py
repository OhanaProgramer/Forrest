"""Object detections from the camera + Hailo, as plain data.

The Hailo YOLOv8 model (with its built-in NMS step) returns one array per
COCO class, each row `[y0, x0, y1, x1, score]` in 0..1 image coordinates.
`parse_nms` turns that into `Detection` objects so everything downstream
(the dashboard, the log, later the follow logic) works without hardware.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

COCO_LABELS = (
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck",
    "boat", "traffic light", "fire hydrant", "stop sign", "parking meter", "bench",
    "bird", "cat", "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra",
    "giraffe", "backpack", "umbrella", "handbag", "tie", "suitcase", "frisbee",
    "skis", "snowboard", "sports ball", "kite", "baseball bat", "baseball glove",
    "skateboard", "surfboard", "tennis racket", "bottle", "wine glass", "cup",
    "fork", "knife", "spoon", "bowl", "banana", "apple", "sandwich", "orange",
    "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair", "couch",
    "potted plant", "bed", "dining table", "toilet", "tv", "laptop", "mouse",
    "remote", "keyboard", "cell phone", "microwave", "oven", "toaster", "sink",
    "refrigerator", "book", "clock", "vase", "scissors", "teddy bear",
    "hair drier", "toothbrush",
)


@dataclass(frozen=True)
class Detection:
    label: str
    score: float
    # box in 0..1 image coordinates: left, top, right, bottom
    x0: float
    y0: float
    x1: float
    y1: float

    def as_record(self) -> dict:
        return {"label": self.label, "score": round(self.score, 3),
                "box": [round(v, 4) for v in (self.x0, self.y0, self.x1, self.y1)]}


def parse_nms(per_class: Sequence[Iterable[Sequence[float]]], threshold: float = 0.5,
              labels: Sequence[str] = COCO_LABELS) -> list[Detection]:
    """Hailo NMS output (one row list per class) -> detections above threshold,
    highest score first."""
    out = []
    for class_id, rows in enumerate(per_class):
        label = labels[class_id] if class_id < len(labels) else f"class_{class_id}"
        for row in rows:
            y0, x0, y1, x1, score = (float(v) for v in row[:5])
            if score < threshold:
                continue
            clamp = lambda v: min(max(v, 0.0), 1.0)
            out.append(Detection(label, score, clamp(x0), clamp(y0), clamp(x1), clamp(y1)))
    out.sort(key=lambda d: d.score, reverse=True)
    return out
