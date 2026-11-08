# HANDOFF — MacBook ⇄ forrest-jr

Short-lived work passed between the two machines, synced by git. This is a
queue, not a record: design decisions go to Continuity (from the MacBook), and
finished items are deleted from here.

## Rules
1. `git pull` before editing this file; commit and push right after. Keep commits small.
2. Each item: direction tag, date, one-line ask, and who owns it.
   `[mac→jr]` = work for the Pi. `[jr→mac]` = work for the MacBook.
3. When done: add a `Done YYYY-MM-DD:` line with the result, and delete the item
   in the next session after the receiving side has seen it.
4. Anything durable (a decision, a milestone result) is moved to Continuity by
   the MacBook session. forrest-jr cannot write to Continuity, so it proposes edits here.
5. Who edits code: either machine may change this repo. Hardware drivers and
   bench runs are done on forrest-jr; say in the item which machine owns a change.

## Resume here (end of day 2026-11-04)
- Done today: hoverboard removed; camera + Hailo verified (29.9 fps); `forrest view`
  window; dashboard steps 1-2 at http://100.123.84.14:8090/ (dark, tailnet only).
- `forrest dash` (status only, no camera) now **starts at boot** as the user service
  `forrest-dash` (`pi/systemd/`, linger on). Camera and Hailo are free.
  Control: `systemctl --user status|restart|stop forrest-dash`; logs: `journalctl --user -u forrest-dash`.
  For detections, stop the service and run `.venv/bin/forrest dash --camera` by hand.
- Open: green cast on the ov5647 (white measures about R 98 / G 168 / B 166);
  detection log; camera panel on the page.
- Mac to-do: the Continuity edits below. The hoverboard "why" still needs Jacque.

## Now (forrest-jr, from 2026-11-04)
1. **HAT + camera ops test** on the Pi (Hailo-8 + ov5647): live detection runs,
   frame rate and temperature are measured, and results are logged here.
   - **Done 2026-11-04 (first pass):** ov5647 detected (modes up to 2592x1944).
     YOLOv8s on Hailo-8 at 1280x960, **30.0 fps** for 20 s (588 frames), Pi
     52-54 C, `throttled=0x0`. Detection seen: person 92%; one false "kite" 46%
     on the ceiling light. Notes: the image has a **green cast** (likely the
     tuning file or a NoIR module; to check). `rpicam-still` with the Hailo
     stage captures before the model loads ("HailoRT not ready"), so use video
     for proof frames. Artifacts in `data/camtest/` (git-ignored).
   - Next: fix the green cast; a longer soak (10 min) to see temperature
     settle; get detections out as data (JSON), which the status site will need.
2. **Forrest dashboard** (`forrest dash`, http://100.123.84.14:8090/, tailnet only).
   - **Done 2026-11-04, step 1, hardware strip:** CPU (% / GHz / temp), AI HAT
     temp, power (throttle + input V), fan rpm, memory, disk, Wi-Fi (dBm, IP,
     rates), Tailscale, uptime. Green/amber/red limits in `dashboard/status.py`
     LIMITS. No sudo. Server cost 0.55% of one core while polled every 2 s.
     Camera is opt-in (`--camera`) so `forrest view` can run alongside.
   - **Done 2026-11-04, step 2, visual pass:** 10 stat tiles with 2-min sparklines
     or limit meters; status = icon + word, never colour alone; 30-min history
     charts (temperature with caution/throttle lines, CPU load, network) with
     hover readouts; readings table with sources; light + dark. Server samples
     every 2 s in the background (30-min ring buffer, `/api/history`).
     Palette: dataviz reference palette, validated in-browser (no Node needed).
   - **Done 2026-11-04, start at boot:** user service `forrest-dash` (pi/systemd/,
     install with `pi/systemd/install-dash.sh`). Binds the pinned Tailscale IP and
     retries every 5 s until tailscale0 is up (no silent 127.0.0.1 fallback).
     Verified running + HTTP 200; not yet proven across a real reboot.
   - Next, one at a time: camera panel, detection log.
   - **Done 2026-11-08:** Now tiles grouped as Thermal / Power / System / Network
     (commit 11f0b18). Not yet checked in a browser; restart `forrest-dash` to load it.
3. **Pico 2 bench + monitoring (new focus from 2026-11-08, forrest-jr owns it).**
   Jacque: develop the Pico 2 locally on Jr for now. The aim is to test the hardware
   and build the monitoring process and page, so a running robot can be watched
   over the web.
   - Board: Pico 2 (RP2350), MicroPython 1.29.0, USB serial `1c4e1cea890aaffb`,
     `/dev/ttyACM0`. On the board: the bench firmware (`main.py`) + `protocol.py`.
     Boot output: `READY`, then `FAILSAFE 1499901`, which means throttle cut to
     neutral (1.5 ms) 500 ms after boot with no commands. That is the correct behaviour.
   - **Done 2026-11-08:** copied both files off the board into the repo. The MacBook's
     2026-11-05 drive files were learning tests and are no longer used (Jacque); the
     repo copy is the source now.
   - **Done 2026-11-08, firmware split into modules** (`firmware/pico/drive/`):
     `comm.py` (non-blocking serial: assembles whole lines, never waits on a half
     line; drops lines over 64 chars), `heartbeat.py` (Pi-is-alive watchdog),
     `protocol.py` (parse + pulse mapping), `main.py` (pins + loop). Pure parts have
     host tests (`tests/test_pico_{comm,heartbeat,protocol}.py`, 34 tests pass).
     `STAT` now ends with `trips` (failsafe trips since boot). Deploy:
     `firmware/pico/deploy.sh` (mpremote, in `.venv`). Deployed and on the board.
   - **Bench, 2026-11-08, on the board (no ESC/servo):** split lines are assembled,
     bad and over-long lines are rejected, `?` does not feed the heartbeat.
     **P2 failsafe timing: trip 514 ms after the last command, 5 of 5 trials**
     (500 ms limit + one 5 ms pass + USB). Loop `max_gap` 11-16 ms.
     Found: when a host opens the port, the Linux tty briefly echoes the Pico's own
     output back, so the Pico logs `BAD READY`. Harmless (it doesn't feed the
     heartbeat); the Pi driver must open the port raw and ignore startup lines.
     Ctrl-D no longer soft-resets the board (main.py owns stdin); use `mpremote reset`.
   - Plan, one step at a time:
     a. ~~`mpremote` on Jr~~ done.
     b. udev rule for a stable `/dev/forrest-pico` name (needs sudo once).
     c. ~~`src/forrest/drivers/pico.py`~~ **done 2026-11-08**: parses READY/OK/BAD/
        FAILSAFE/STAT (never raises; unreadable = UNKNOWN), finds the Pico by USB id
        (2e8a:0005), opens it **exclusive** (a second program is refused; verified),
        drops the startup echo. `status()` polls `?` (no heartbeat);
        `send_command()` is the heartbeat, for a controller only. 18 tests
        (`tests/test_pico_driver.py`). `forrest pico check` = read-only poll; on the
        board: link UP, ~6-7 ms round trip. The udev rule (b) is no longer needed for
        finding the port; skip it unless a second Pico appears.
        Jacque ran the step-1 checks on the board 2026-11-08: all good.
     d. **Built 2026-11-08, not installed yet:** `forrest pico monitor`
        (`src/forrest/health/pico_monitor.py`, 7 tests). Polls `?` once a second (read-only);
        link down after 3 s without an answer; reconnects by itself after an unplug.
        State: `$XDG_RUNTIME_DIR/forrest/pico.json`, replaced atomically each poll. It
        stays behind when the monitor stops, so readers must treat an old `updated` as
        "monitor not running". Log: `data/pico/pico_YYYYMMDD.jsonl` (events + link
        changes + a sample every 10 s, ~1.3 MB/day). Ran 8 s on the board: 8/8 answered,
        ~5 ms. Service: `pi/systemd/forrest-pico.service`, install with
        `pi/systemd/install-pico.sh`. Once installed, stop it before mpremote/deploy.sh.
        Original plan for d: the `forrest-pico` user service, the only program that opens the port. It
        polls `?` (STAT) and logs every line to `data/`. It writes the latest
        state to a file for the dashboard. It does **not** send drive commands,
        so the Pico stays in failsafe.
     e. Pico panel on `forrest dash`: link up/down (data older than a few seconds =
        down), failsafe state + trip log, loop `max_gap_ms`, command age. Read-only.
     f. Bench tests: P1 link (unplug → "link down"); P2 failsafe timing (send
        commands, stop, measure the trip against 500 ms); P3 30-min telemetry soak.

## Open

### [jr→mac] 2026-11-08 — Continuity edits (MacBook only)
- **DECISIONS.md**, append:
  `## 2026-11-08 — Forrest Jr: Pico 2 bench + monitoring page next`
  - Jacque: the Pico 2 is developed locally on forrest-jr for now. The focus is
    testing the hardware and setting up the monitoring process and pages, so a
    running robot can be watched over the web (`forrest dash`, tailnet only, read-only).
  - The monitor only reads the Pico (status polls). It never sends drive commands.
- **02_Projects/Forrest/SYSTEMS.md**: add the Pico bench steps P1–P3 (link, failsafe
  timing, telemetry soak) as the current step.
- **USER.md / local_IT**: forrest-jr now boots from a Samsung 860 EVO 250G SSD over
  USB (seen 2026-11-08), not an SD card. Desktop session switched to X11 (rpd-x) for
  xscreensaver.

### [jr→mac] 2026-11-04 — Continuity edits (MacBook only)
- **DECISIONS.md**, append:
  `## 2026-11-04 — Forrest Jr: hoverboard dropped; RC truck later; camera first`
  - Jacque dropped the hoverboard drive. All hoverboard hardware and software were
    deleted (repo commit "Drop hoverboard drive"; history remains in git).
    Supersedes the vehicle line of "2026-10-22 — Forrest Jr: control test bed,
    bench first, hoverboard base".
  - The drive base will be the 1/10 RC truck, the recorded fallback. That is future work.
  - Current focus: the HAT/camera ops test, then a mini status website run from
    the Pi. Why the hoverboard was dropped: _Jacque to fill in_.
- **02_Projects/Forrest/SYSTEMS.md**: mark the hoverboard milestones (M0–M7) as
  dropped, set the drive base to the 1/10 RC truck (future), and add the camera
  ops test as the current step.
- **00_System/USER.md**, Machines line: replace
  `forrest-jr 100.123.84.14 (Raspberry Pi, SSH on, offline since Oct 27)` with
  `forrest-jr 100.123.84.14 (Raspberry Pi 5, SSH on; Hailo-8 verified 2026-11-04)`.
- **DECISIONS.md**, append: `## 2026-11-04 — Forrest dashboard lives in the repo,
  served by the robot` — Forrest's visualisation page is part of the Forrest repo
  and runs on forrest-jr (later Sr), not on the mini. Why: it reads the robot's own
  drivers and data and must change in the same commit as them; it goes where the
  robot goes. Tailnet-only, read-only.
- **00_System/README.md** (Agent access routes): add one line saying that work
  between the MacBook and forrest-jr crosses through this repo's `HANDOFF.md`.
