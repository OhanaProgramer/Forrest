"""Apply Forrest Jr's settings to an EFeru FOC firmware checkout.

Usage: python3 forrest_config.py <path-to-efoc-checkout>

Every change is a plain text substitution that must match exactly once, so an
upstream change makes this fail loudly instead of silently skipping a setting.
Reasons for each value: Continuity 02_Projects/Forrest/SYSTEMS.md (Drive card).
"""
import re
import sys
from pathlib import Path

# (file, old, new, why)
EDITS = [
    # Build only the serial-control variant.
    ("platformio.ini",
     ";default_envs = VARIANT_USART ",
     "default_envs = VARIANT_USART ",
     "build the serial-control variant"),
    # Bench limits: gentle until the wheels are proven. Raise later, one step at a time.
    ("Inc/config.h",
     "#define I_MOT_MAX       15 ",
     "#define I_MOT_MAX       5  ",
     "bench: 5 A per motor (stock 15 A)"),
    ("Inc/config.h",
     "#define I_DC_MAX        17 ",
     "#define I_DC_MAX        7  ",
     "bench: keep I_DC_MAX = I_MOT_MAX + 2 A"),
    ("Inc/config.h",
     "#define N_MOT_MAX       1000 ",
     "#define N_MOT_MAX       200  ",
     "bench: 200 rpm (about 1.7 m/s on 6.5-inch wheels)"),
]

# Inside the VARIANT_USART block only: each command sets one wheel (left, right).
TANK_OLD = "  // #define TANK_STEERING              // use for tank steering"
TANK_NEW = "  #define TANK_STEERING                 // use for tank steering"


def apply(root: Path) -> None:
    for rel, old, new, why in EDITS:
        p = root / rel
        text = p.read_text()
        n = text.count(old)
        if n != 1:
            sys.exit(f"{rel}: expected 1 match for {old!r}, found {n}. Upstream changed; update forrest_config.py.")
        p.write_text(text.replace(old, new))
        print(f"  {rel}: {why}")

    cfg = root / "Inc/config.h"
    text = cfg.read_text()
    m = re.search(r"#ifdef VARIANT_USART\n(.*?)\n#endif", text, re.S)
    if not m or m.group(1).count(TANK_OLD) != 1:
        sys.exit("config.h: TANK_STEERING line not found once in the VARIANT_USART block.")
    block = m.group(1).replace(TANK_OLD, TANK_NEW)
    cfg.write_text(text[: m.start(1)] + block + text[m.end(1):])
    print("  Inc/config.h: TANK_STEERING on (command = left wheel, right wheel)")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    apply(Path(sys.argv[1]))
