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

## Now (forrest-jr, from 2026-11-04)
1. **HAT + camera ops test** on the Pi (Hailo-8 + ov5647): live detection runs,
   frame rate and temperature are measured, and results are logged here.
2. Then: design a small **status website served from the Pi** (camera, Hailo,
   power/heat, LIDAR). Scope it before building anything.

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
- **00_System/README.md** (Agent access routes): add one line saying that work
  between the MacBook and forrest-jr crosses through this repo's `HANDOFF.md`.
