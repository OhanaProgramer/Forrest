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

## Resume here (2026-11-22, forrest-jr)
- **Jr is headless now** (Jacque ran `raspi-config nonint do_boot_behaviour B1`): boots to
  `multi-user.target`, no desktop, no autologin. The user services still start at boot
  (linger on). Git uses `~/.ssh/forrest_deploy` (no passphrase, no keyring needed). After the
  reboot at 12:34: forrest-dash/pico/lidar all came up active, camera + Hailo at 30.0 fps,
  `/stream` serving, HTTP 200, 859 MB RAM used (was 1,743 MB with the desktop), 47 C, throttled=0x0.
  This also completes the **reboot test with the camera at boot** (3432367). Undo: `do_boot_behaviour B4`.
- Done today (commits f29f579..3432367): LIDAR dashboard view + `forrest-lidar` monitor service;
  monotonic-clock fixes for the history sampler and camera fps; forrest-dash runs `--camera` at boot.
  SSH from the MacBook, the dashboard and the camera stream were all tested by Jacque. `git stash drop` done.
- **Next: bench B1.** Jacque is plugging in the RPLIDAR C1 (`/dev/ttyUSB0`; the monitor is waiting
  for it) → watch the radar go live. Then: the drive Pico back on USB + P3 soak; trim the
  checklist (kill-switch items out); TQi receiver test (no pulses or neutral with TX off?);
  Wi-Fi drop with the camera running (still untested).
- Still open: confirm the Claude token was rotated; `~/.bashrc.bak-20261106090231` remains
  (check it for the old token, then delete).
- Mac to-do: pull; apply the queued Continuity edits (11-21, 11-10, 11-08, 11-04); add to
  USER.md/local_IT: forrest-jr is headless (console boot) from 2026-11-22.

## Previous (end of day 2026-11-21, forrest-jr)
- Done today: fixed ~/.bashrc (broken CLAUDE_CODE_OAUTH_TOKEN lines; backup
  ~/.bashrc.bak-2026-11-21, chmod 600). Repo reconciled with origin: the stashed dashboard
  draft was already upstream (11f0b18), so upstream was kept; 78 tests pass.
  RC car on hand (Now item 5). Integration checklist:
  https://claude.ai/artifact/EtfnFqFpPchsKh8wkbou4Q (ticks save there).
- **Held for tomorrow (Jacque):** rotate the Claude token (it showed in a pasted error), then
  delete the .bashrc backup; `git stash drop` (old dashboard draft); restart forrest-dash
  (still running pre-pull code); start Phase 0 of the checklist.
- **Decided tonight (Jacque): keep the transmitter as Jr's kill switch; "no transmitter" is a
  Sr goal.** UWB and the custom radio kill switch were a big requirement jump for Jr, so they're
  parked for Sr (see the 11-21 Open items; queue them to PARKING_LOT, not DECISIONS, as Sr
  ideas). How the transmitter kills it, through the drive Pico (receiver → Pico → ESC/servo):
  1. Any trigger/wheel input past a dead zone locks the Pi out. Control stays manual after you
     let go, until a deliberate hand-back (dashboard button or stick gesture).
  2. Lost receiver signal means neutral, and the Pi may not drive.
     **Test first:** does the TQi receiver stop sending pulses with the transmitter off, or
     send neutral pulses? If it sends neutral, the Pico can't detect the loss and #1 is the
     kill switch.
  3. Pi silent means neutral (the existing Pico failsafe, 514 ms measured).
  Tomorrow: trim the checklist (move the 7 kill-switch items + "retire the transmitter" out;
  keep the IMU flip stop). Buy only the IMU + STEMMA QT cables; no Feather radios, no UWB.
- (Superseded by the line above) Discuss first thing: UWB runner tag (Open item below). Don't buy the Feather RFM69
  radios until that's decided. The IMU and the STEMMA QT cables are fine to buy either way.
- Nothing left holding the camera or Hailo. forrest-dash and forrest-pico are running as usual.
- Mac to-do: pull; apply the queued Continuity edits (11-21, 11-10, 11-08, 11-04).

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
     **Installed + running 2026-11-08** (Jacque ran install-pico.sh; unplug test passed:
        link lost at 14:46:08, back by itself at 14:46:20).
     e. **Done 2026-11-08:** Pico group on `forrest dash` (`src/forrest/dashboard/pico.py`,
        7 tests): tiles Pico link / Drive output / Pico loop / Failsafe trips, plus a
        "Pico events" list (last 10). Reads the monitor's state file; never opens the
        port. Not plugged in = caution; plugged in but silent = at limit; monitor stopped
        (state older than 5 s) = no data. Failsafe is "ok" while nothing drives; make it
        a warning once a controller exists. New limit `pico_gap_ms` caution 50 / limit 150.
        Checked live: desktop + phone screenshots, and monitor stop -> "no data" -> start -> up.
        **Status lights, 2026-11-08:** a bar of red/yellow/green lights (one per group,
        worst tile wins) replaces the header summary. Green groups are folded; yellow/red
        open by themselves and close again when green. A click overrides that and is
        remembered in that browser (localStorage). A manual close is dropped if the group
        gets worse. History is folded and opens by itself on any red. Checked: all-green
        view and a simulated Pico link-down. Clicking was not tested headless: try it.
        **Page layout, 2026-11-08:** header = lights; left sidebar = always-on numbers
        (Environment, Position, Robot: `dashboard/sidebar.py`, 3 tests); main = two live
        views, **Radar** (LIDAR top-down, frame only until B1) and **Camera** (stream with
        `--camera`, otherwise a note). The health groups, Pico events and History open as a
        drawer over the views (full screen on a phone). Auto-open now waits for 3 samples
        (~6 s) of yellow/red, so a CPU spike only flashes the light. A manual close is
        cleared once the group is green again. Checked: desktop + phone screenshots; a
        real CPU spike opened the drawer before the 6 s wait was added. Not clicked: the
        drawer's Close button.
        **Reboot test 2026-11-08 (kernel now 6.18.60):** forrest-dash and forrest-pico both came
        up by themselves; camera (ov5647) detected; `forrest dash --camera` worked for Jacque.
        **Offline handling, 2026-11-08:** after 6 s without the Pi, the camera's last frame is
        dropped for an OFFLINE card (last-frame time), the radar says OFFLINE, lights/sidebar grey
        out, header says "OFFLINE since ...". Reconnects by itself; a dropped stream alone retries
        after 2 s. FPS is now a badge on the image. Checked with a stand-in server that stops
        answering (screenshot). Not checked: a real Wi-Fi drop with the camera running.
        Next for the views: B1 (LIDAR on the bench) -> `forrest-lidar` service (same pattern
        as forrest-pico) -> live radar; then the camera inside the boot service.
        Original plan for e: Pico panel on `forrest dash`: link up/down (data older than a few seconds =
        down), failsafe state + trip log, loop `max_gap_ms`, command age. Read-only.
     f. Bench tests: P1 link (unplug → "link down"); P2 failsafe timing (send
        commands, stop, measure the trip against 500 ms); P3 30-min telemetry soak.
4. **Second Pico: the Pico W sensor board (from 2026-11-10, forrest-jr owns it).**
   Jacque: two separate boards on the Pi's USB. Drive Pico 2 = safety only; Pico W =
   sensors (BME688 at 0x77, INA219 at 0x40, STEMMA QT; cable not here yet).
   - **Done 2026-11-10:** Pico W reflashed from Arduino to MicroPython 1.29.0
     (`RPI_PICO_W`, RP2040). Serial `e6616408430b7439` under MicroPython (Arduino showed
     `086461E639740B43`: re-check after any reflash). Filesystem empty, no firmware yet.
   - **Done 2026-11-10, boards by serial number** (commit 6127fa1): every MicroPython
     board reports USB id 2e8a:0005, so the driver now picks by serial (`BOARDS` in
     `drivers/pico.py`; no fallback to "any Pico"). `forrest pico list`,
     `forrest pico check --board`, `deploy.sh` targets `id:<drive serial>`.
     Proven with both plugged in: Pico W took ttyACM0, drive took ttyACM1; the monitor
     opened ACM1 only; `deploy.sh` landed on the drive (files "Up to date", drive rebooted),
     the Pico W stayed empty.
   - **Done 2026-11-10, dashboard** (commit 13d3962): group "Picos" adds a Sensor Pico
     tile (USB presence only, port never opened) and an "Unknown Pico" caution for a
     MicroPython board not in `BOARDS`. Checked via `/api/status`; not looked at in a browser.
   - Next: `firmware/pico/sensors/` skeleton (`READY sensors`, readings-on-request,
     "no sensor" until wired, host tests, its own deploy by serial) → sensor monitor →
     tiles. Then BME688 + INA219 when the cable arrives. Read every few seconds;
     BME688 trigger-then-collect so a read never blocks. INA219 range: ask Jacque what it measures.
5. **RC car: Jr's drive base (on hand 2026-11-21, forrest-jr owns integration).**
   Starts after the compute-core checkout (bench B1/B2 + sensors). Checklist:
   https://claude.ai/artifact/EtfnFqFpPchsKh8wkbou4Q (phase 7).
   - **Done 2026-11-21:** drives on its own transmitter (Jacque tested, stock setup).
   - **Parts (Traxxas Slash 2WD Brushless, model 58434-4).** Per the Traxxas page / a
     retailer listing; check each against the car and the manual:
     | Part | What it is | Check on the car |
     |---|---|---|
     | ESC | Velineon VX3, waterproof brushless; Sport / Race / Training profiles | BEC voltage; LiPo low-voltage detection on; signal plug |
     | Motor | Velineon V3200, 3200 Kv sensorless brushless (retailer listing only) | label on the can |
     | Steering servo | Traxxas 2057, metal gear, waterproof | end stops in µs |
     | Radio | TQi Sport 2.4 GHz, **2 channels** (steering, throttle), TSM | receiver failsafe goes to neutral with TX off |
     | Drive battery | one 2S or 3S LiPo (VX3 does not take NiMH); bay 166 x 49 x 28 mm | which pack; separate from the compute 3S |
   - Integration notes:
     - Only 2 channels, so there is no spare switch channel for auto/manual. Manual
       override has to come from the sticks: any stick input wins over the Pi.
     - TSM (stability management) runs in the receiver. Note whether it changes the
       pulses the Pico reads, and decide on/off for the bench.
     - Keep Training Mode (reduced power) on the ESC for the first rolls.
     - The Pico sits between the receiver and the ESC/servo (servo-PWM, common ground,
       signal wires only). Its power must not depend on the Pi's USB.
     - **Jacque, 2026-11-21: the goal is no transmitter at all.** It stays only as a
       development safety tool until the runner kill switch is proven (decision queued
       below for Continuity).

## Open

### [jr→mac] 2026-11-21 — UWB runner tag: first cost look (discuss in the morning; nothing bought)
Idea (Jacque): the runner carries a device, so the cart knows exactly where he is.
UWB (ultra-wideband, the radio in AirTags) times radio pulses between a tag on the runner
and anchors on the cart: distance to ~10 cm and, with 2+ anchors or an angle-measuring
(PDoA) anchor, direction too. It isn't affected by sun or dark, and it can't mistake another
person for him. It could do three jobs: follow (area 3), a kill-switch button, and a
dead-man stop when the link drops (area 11). The LIDAR stays for obstacles.
Prices from distributor pages, undated; check before buying:
| Option | What you get | Rough cost for 1 tag + anchors | Effort |
|---|---|---|---|
| Qorvo DWM3001CDK dev kit (DW3110 UWB + nRF52833, has an accelerometer) | DIY; ~$25–32 each at US distributors (RFMW/Octopart $29.50); lead times vary | 3 boards ≈ $90–100 (tag + 2 anchors) | Most: firmware from Qorvo's SDK, we write the ranging + angle math |
| Makerfabs ESP32 UWB DW3000 | DIY, Arduino-friendly; ~€50–60 each (EU retailer; no current US price found) | 3 boards ≈ $150–180 | Medium: Arduino examples exist |
| Haorutech ULM3 PDoA anchor + tag (RobotShop) | Ready-made "UWB following": one anchor gives distance ±5 cm and angle over a 120° field | ≈ $250 for the set | Least: read distance + angle over serial |
Notes: a 120° field means a single PDoA anchor only sees one side of the cart; aim it at his
side, or add a second. Questions for the morning: wrist or belt; battery life for a
multi-hour run; where the kill-switch button lives; whether the tag replaces the RFM69
radios.

### [jr→mac] 2026-11-21 — Continuity edits: transmitter retired later, runner kill switch, IMU (MacBook only)
- **DECISIONS.md**, append: `## 2026-11-21 — Forrest Jr: no transmitter in the end; runner kill switch replaces it`
  - Jacque: Jr should not need the RC transmitter. Supersedes "the Pico reads the RC
    receiver; manual override wins" (2026-10-22 Jr direction).
  - Until the kill switch passes its tests, the stock TQi (2-channel, no spare switch) stays
    in use as a development safety tool for the bench, first rolls and M5. The override
    latches: touching the sticks takes control, and handing back takes a deliberate act.
    No transmitter signal means stop.
  - **Runner kill switch = heartbeat, not a button signal.** A handheld radio sends "alive"
    about every 50 ms. A radio on the car holds a run-permit wire to the drive Pico high only
    while those messages arrive. Pressing the button, a dead battery, out of range or a
    cut wire all mean stop, within about 250 ms (starting value). It goes straight to the
    drive Pico and never through the Pi.
    Why not a cheap RF key fob: it only transmits on a press, so it can't tell when its
    signal is lost.
  - **IMU for tilt / flip / impact** (6-DoF accel + gyro, STEMMA QT) on the sensor Pico W.
    Stop on upside down, tipped over or a hard impact. v1 path: sensor Pico → Pi → stop
    command. The kill switch and the Pico failsafe remain the hard safety layer. Move the
    flip stop onto the drive Pico later if the Pi path proves too slow.
    An accelerometer can't measure speed ("too fast") reliably, because integrating it
    drifts within seconds. Speed needs wheel speed (a Hall sensor + magnet on the drivetrain,
    read by the drive Pico) or GPS. That's a later part.
- **SYSTEMS.md** area 11 (Safety): add the runner kill switch design and the tests
  (press → stop, handheld off → stop, range 5–10 m while running).
- **SYSTEMS.md** Jr parts (all Adafruit; buy now for the next milestones):
  | Part | Adafruit PID | Qty | Serves |
  |---|---|---|---|
  | Feather RP2040 RFM69 Packet Radio, 868/915 MHz (use 915 in the US) | 5712 | 2 | kill switch (handheld + car) |
  | ISM330DHCX 6-DoF IMU, STEMMA QT (-40 to +105 °C); or LSM6DSOX, PID 4438 | 4502 | 1 | flip / tilt / impact |
  | STEMMA QT to male header cable, 150 mm (for a bare Pico W or breadboard) | 4209 | 2 | sensor chain to Pico W |
  | STEMMA QT cable, JST SH both ends (sensor to sensor) | check | 2 | daisy chain |
  | Small LiPo + momentary button + enclosure for the handheld | check | 1 | kill switch handheld |
  If the Pico W has male headers soldered on, it needs the STEMMA QT cable with female
  sockets instead of 4209.
  I²C addresses don't clash: INA219 0x40, IMU 0x6A, BME688 0x77.

### [jr→mac] 2026-11-09 — Camera architecture for car-detection (explored; park until that phase; nothing to buy)
Propose into DECISIONS.md / SYSTEMS.md:
- **Two independent cameras, not a stereo pair.** A stereo pair (~2 ft baseline for depth) was
  considered and dropped — a rigid, vibration-stable baseline + calibration on a moving cart is too
  fragile. The one thing stereo would add is ranging a *far* car (the 12 m LIDAR can't reach it);
  revisit only if single-camera ranging proves insufficient.
- **Roles:** Cam 1 = **rear telephoto** = overtaking-car detection (primary threat; Jacque runs facing
  traffic, cars overtake from behind). Cam 2 = **front wide** = cross-traffic / forward hazards, and a
  follower backup only if the LIDAR can't fully follow. Following stays the LIDAR's job.
- **Lens drives range, not height** (range ≈ warning time; a tighter lens ~doubles range; height only
  helps sightline/occlusion). Tele market: Pi HQ (IMX477) + an 8–50 mm C-mount zoom to learn the
  FoV↔range tradeoff, then a fixed telephoto.
- **Compute:** one Pi + Hailo handles two cameras if the *inference* is duty-cycled (one hot, the other
  on threat; cameras kept warm to avoid startup latency). Both running full-tilt at once is the trigger
  to reconsider a 2nd processor.
- **Sr option (parked):** a dedicated car-detection processor — a 2nd Pi+Hailo or a Jetson. Decide the
  chip and the camera *together*: automotive-grade sensing (GMSL = single coax up to ~15 m + rugged;
  global shutter = clean capture of fast cars) lives in the Jetson ecosystem. Let Jr measure the need first.

### [jr→mac] 2026-11-09 — Jr camera test plan (uses the ov5647 + Hailo on hand; no buy; after/alongside B1)
- **Forward-solo pipeline test:** prove capture → Hailo → detections as JSON → dashboard with the one
  forward ov5647. Transfers wholesale to the rear detector (same pipeline, different lens/aim).
- **Roadside oncoming-traffic test (Jacque's idea):** camera at the roadside facing oncoming traffic,
  detect real cars. An approaching car growing in the frame is the *same* signal whether it's oncoming at
  the roadside or an overtaker seen by the rear cam — so this validates the rear-detector's core job with
  no moving robot. Record raw + detections; measure **first-detection range** (→ warning time at road
  speed), false pos/neg, and day/dusk/dark. Also the test that **empirically picks the lens**: if the wide
  ov5647 detects cars too late, that is the data that justifies the telephoto and its focal length.

### [jr→mac] 2026-11-08 — Sensor shopping list (Jacque has none yet)
- Air temp / humidity / pressure: BME280- or BME688-class breakout (I2C, on the Pi), ~$10-20.
- GPS: u-blox M8/M9 USB module (on the Pi), ~$20-40.
- Battery voltage: resistor divider into a Pico ADC pin (reported in the Pico's STAT).
- The LIDAR (RPLIDAR C1) exists; it is just not plugged in. B1 not run yet.

### [jr→mac] 2026-11-10 — Continuity edits (MacBook only)
- **DECISIONS.md**, append: `## 2026-11-10 — Forrest Jr: two Picos, drive and sensors`
  - Jacque: sensors go on a separate board (Pico W) on the Pi's USB, not on the drive
    Pico 2 (the AI HAT covers the Pi's GPIO; the drive Pico stays safety-only, so a
    sensor bug or loose I2C wire can't reach the failsafe). Sensor data is low priority:
    read every few seconds.
  - The Pi picks each board by USB serial number, never by USB id (all MicroPython
    boards share 2e8a:0005).
  - Power: two Picos + sensors add ~0.1 A on the Pi's 1.6 A USB budget (5 A supply);
    the SSD and, later, the LIDAR are the big loads. On the vehicle the drive Pico must
    not depend on the Pi's USB for power.

### [jr→mac] 2026-11-08 — Continuity edits (MacBook only)
- **DECISIONS.md**, append: `## 2026-11-08 — Forrest dashboard layout: lights, sidebar, two views`
  - Status lights per group across the top (red/yellow/green; internal page, so colour alone
    is acceptable). Always-on sidebar: environment, position, robot (battery, Pico, drive).
    Main area: two live views, LIDAR radar and camera. Health detail and history open as a
    drawer only when needed or clicked. A future map may load OpenStreetMap tiles over the
    viewer's phone connection (Jacque: OK); robot data stays on the tailnet.
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
    the Pi.
  - **Why the hoverboard was dropped:** the open-firmware hack needs two broken-out
    control lines per board — SWD to flash, UART to drive — but the HY-A02C exposed
    only one clean 4-pin header; reaching the second would have meant soldering to the
    MCU's ~0.5 mm legs, past Jacque's clean-build bar ("clean shot, not another
    gamble"). Both candidate boards were returned: the Gyroor G13 (chip YY3061, in no
    open firmware project — not hackable) and the HY-A02C (too fiddly). Jr's drive is
    now an off-the-shelf 1/10 hobby-grade RC car — standard ESC + steering servo driven
    by the Pico over servo-PWM — which needs no flashing and no chip-level soldering.
    The hub-motor + off-the-shelf serial controller (VESC/ODrive) build is parked as
    the future/Sr option.
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
