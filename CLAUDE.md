# Working rules for this repo

- **Continuity is the record.** Design decisions and their reasons live in
  Continuity → `02_Projects/Forrest/` (SYSTEMS.md, PREBUY_IDEAS.md) and
  `00_System/DECISIONS.md`. This repo holds code, CAD and runbooks. Don't
  duplicate design rationale here; point to it.
- **Bench before vehicle.** Current success line: the sensor-and-power module
  working stand-alone (B1, B2 in docs/BENCH.md). One milestone at a time.
- **Hardware behind drivers.** Only `src/forrest/drivers/` touches hardware.
  Everything else works on `Scan` objects so it runs against recordings.
- **Time-critical control lives on the Pico**, not in Linux: motor commands,
  failsafe, e-stop, battery voltage, wheel speed.
- **Tests run without hardware.** Add a test with every parser or logic change.
- **Say what's untested on hardware.** Code written from a datasheet is
  labelled as such until it has run on the real part.
- **Plain language for Jacque:** explain what a concept decides, where it
  shows up and what breaks without it; run the numbers yourself.
- Python 3.11+ (the Pi runs Raspberry Pi OS Trixie, Python 3.13), venv in `.venv`.
