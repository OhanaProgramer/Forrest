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

## Open

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
