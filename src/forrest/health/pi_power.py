"""Read the Pi's own power and heat warnings.

The Pi firmware keeps a bit-field of problems it has seen since boot, read with
`vcgencmd get_throttled`. For B2 the question is simple: during an hour on the
battery, did the Pi ever see low voltage? If bit 16 is clear, the power supply
is good enough.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from typing import Optional

# bit -> meaning (the "now" bits 0-3, the "since boot" bits 16-19)
FLAGS = {
    0: "under-voltage now",
    1: "CPU frequency capped now",
    2: "throttled now",
    3: "soft temperature limit now",
    16: "under-voltage has occurred",
    17: "CPU frequency capping has occurred",
    18: "throttling has occurred",
    19: "soft temperature limit has occurred",
}


@dataclass(frozen=True)
class ThrottleState:
    raw: int

    @property
    def problems(self) -> list[str]:
        return [msg for bit, msg in FLAGS.items() if self.raw & (1 << bit)]

    @property
    def undervoltage_seen(self) -> bool:
        return bool(self.raw & ((1 << 0) | (1 << 16)))

    @property
    def ok(self) -> bool:
        return self.raw == 0


def parse_throttled(text: str) -> ThrottleState:
    """Parse output like 'throttled=0x50005'."""
    m = re.search(r"throttled=(0x[0-9a-fA-F]+)", text)
    if not m:
        raise ValueError(f"unexpected vcgencmd output: {text!r}")
    return ThrottleState(int(m.group(1), 16))


def parse_temp(text: str) -> float:
    """Parse output like "temp=48.3'C"."""
    m = re.search(r"temp=([0-9.]+)", text)
    if not m:
        raise ValueError(f"unexpected vcgencmd output: {text!r}")
    return float(m.group(1))


def _vcgencmd(*args: str) -> Optional[str]:
    try:
        return subprocess.run(["vcgencmd", *args], capture_output=True, text=True,
                              timeout=2, check=True).stdout
    except (FileNotFoundError, subprocess.SubprocessError):
        return None  # not on a Pi


def read_throttled() -> Optional[ThrottleState]:
    out = _vcgencmd("get_throttled")
    return parse_throttled(out) if out else None


def read_temp_c() -> Optional[float]:
    out = _vcgencmd("measure_temp")
    return parse_temp(out) if out else None
