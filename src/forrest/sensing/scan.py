"""Scans, sectors, and the record/replay format.

A `Scan` is one full LIDAR rotation: a list of (angle, distance, quality)
points. Angles are in degrees, 0-360, measured the way the LIDAR reports them
(clockwise, 0 = the LIDAR's forward mark). Mount orientation is handled later
by a single offset, not scattered through the code.

Recordings are JSON Lines: one scan per line. Easy to read, easy to diff,
replayable on any machine with no hardware.
"""

from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Iterator, Optional, Protocol


@dataclass(frozen=True)
class ScanPoint:
    angle_deg: float
    distance_m: float
    quality: int = 0


@dataclass
class Scan:
    timestamp: float
    points: list[ScanPoint] = field(default_factory=list)

    def in_sector(self, start_deg: float, end_deg: float) -> list[ScanPoint]:
        """Points whose angle is within [start, end), wrapping past 360."""
        if end_deg - start_deg >= 360:
            return list(self.points)
        start, end = start_deg % 360, end_deg % 360
        if start <= end:
            return [p for p in self.points if start <= p.angle_deg < end]
        return [p for p in self.points if p.angle_deg >= start or p.angle_deg < end]

    def nearest(self, start_deg: float = 0, end_deg: float = 360) -> Optional[ScanPoint]:
        return min(self.in_sector(start_deg, end_deg), key=lambda p: p.distance_m, default=None)

    # -- serialisation -------------------------------------------------------
    def to_json(self) -> str:
        return json.dumps({
            "t": round(self.timestamp, 4),
            "p": [[round(p.angle_deg, 3), round(p.distance_m, 4), p.quality] for p in self.points],
        })

    @classmethod
    def from_json(cls, line: str) -> "Scan":
        d = json.loads(line)
        return cls(timestamp=d["t"], points=[ScanPoint(a, r, q) for a, r, q in d["p"]])


# Eight 45-degree sectors, named for a LIDAR whose 0 deg points forward.
# Used by the live check tool so "you are a moving blob" is visible over SSH.
SECTORS_8 = [
    ("front", 337.5, 22.5),
    ("front-right", 22.5, 67.5),
    ("right", 67.5, 112.5),
    ("back-right", 112.5, 157.5),
    ("back", 157.5, 202.5),
    ("back-left", 202.5, 247.5),
    ("left", 247.5, 292.5),
    ("front-left", 292.5, 337.5),
]


def sector_nearest(scan: Scan, sectors=SECTORS_8) -> dict[str, Optional[float]]:
    """Nearest distance (m) in each named sector, or None if nothing seen."""
    out = {}
    for name, start, end in sectors:
        p = scan.nearest(start, end)
        out[name] = p.distance_m if p else None
    return out


def to_xy(points: Iterable[ScanPoint]) -> list[tuple[float, float]]:
    """Convert to x (forward) / y (right) metres, for plotting."""
    return [
        (p.distance_m * math.cos(math.radians(p.angle_deg)),
         p.distance_m * math.sin(math.radians(p.angle_deg)))
        for p in points
    ]


# ---------------------------------------------------------------------------
# Sources: anything that yields scans. Live LIDAR and replay look the same.
# ---------------------------------------------------------------------------

class ScanSource(Protocol):
    def iter_scans(self) -> Iterator[Scan]: ...


class ReplaySource:
    """Replay a .jsonl recording, optionally at the original speed."""

    def __init__(self, path: str | Path, realtime: bool = True, loop: bool = False):
        self.path = Path(path)
        self.realtime = realtime
        self.loop = loop

    def iter_scans(self) -> Iterator[Scan]:
        while True:
            prev_t: Optional[float] = None
            with self.path.open() as f:
                for line in f:
                    if not line.strip():
                        continue
                    scan = Scan.from_json(line)
                    if self.realtime and prev_t is not None:
                        time.sleep(max(0.0, min(1.0, scan.timestamp - prev_t)))
                    prev_t = scan.timestamp
                    yield scan
            if not self.loop:
                return


def write_recording(scans: Iterable[Scan], path: str | Path) -> int:
    """Write scans to a .jsonl file; returns how many were written."""
    n = 0
    with Path(path).open("w") as f:
        for scan in scans:
            f.write(scan.to_json() + "\n")
            n += 1
    return n
