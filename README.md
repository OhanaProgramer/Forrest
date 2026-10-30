# Forrest

A runner-safety cart: it runs beside the runner, warns him when a car is coming
at his line, and later carries gear for a run across the US. Personal build.

**Forrest Jr** is the control test bed: a Raspberry Pi 5 + AI HAT brain, an
RPLIDAR C1 and a camera for sensing, a Pico as the safety bridge, on a
repurposed hoverboard (two hub motors, the same layout planned for Sr).

The design record and decisions live in Continuity
(`02_Projects/Forrest/`). This repo holds the code, the CAD and the runbooks.

## Where things are

| Path | What |
|---|---|
| `src/forrest/drivers/` | The only code that talks to hardware (LIDAR, hoverboard board; Pico link, camera later) |
| `src/forrest/sensing/` | Scans, sectors, record/replay |
| `src/forrest/health/` | Pi power and heat checks |
| `src/forrest/tools/cli.py` | The `forrest` command (bench tools) |
| `tests/` | Run anywhere, no hardware: `pytest` |
| `docs/BENCH.md` | Step-by-step for B1 (LIDAR) and B2 (battery soak) |
| `pi/setup_pi.sh` | Set up or rebuild the Pi in one command |
| `firmware/hoverboard/` | Drive board: flow of events H0-H7, firmware settings, Mac setup |
| `firmware/pico/` | Pico safety bridge (MicroPython), B4 |
| `cad/` | OpenSCAD sources; `cad/stl/` ready to print |
| `data/` | Recordings and logs (large files are not committed) |
| `archive/v0_vision_jan26/` | The January 2026 video-first prototype, kept for reference |

## Working on it

```bash
# Mac (or anywhere): develop against recordings
python3 -m venv .venv && source .venv/bin/activate
pip install -e '.[viz,dev]'
pytest
forrest lidar view --replay data/recordings/<file>.jsonl

# Pi: see docs/BENCH.md
```

Loop: edit on the Mac -> commit -> push -> `git pull` on the Pi -> run.

## Bench ladder

| # | Step | Done when |
|---|---|---|
| B1 | LIDAR on the Pi, wall power | Live scan; you show up as a moving blob |
| B2 | Same on the 3S battery | 1 h with the LIDAR spinning, no under-voltage, alarm works. **Success line** |
| B3 | Find Jacque | Live angle + range that follow him at ~1 m |
| B4 | Pico safety bridge | Pi commands go through; unplug the Pi and it stops |
