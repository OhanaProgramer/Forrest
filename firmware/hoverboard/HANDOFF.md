# Hoverboard bring-up — handoff (for a local Claude Code session)

Read this + `README.md` (same folder) + repo-root `CLAUDE.md`. Design rationale
lives in Continuity `02_Projects/Forrest/SYSTEMS.md`.

## Where we are (2026-11-02)
Phase 1 (confirm) is nearly done. Drive pivot settled:
- Gyroor G13 **returned** — not hackable (chip YY3061, in no open project).
- Jr's drive = the **HY-A02C**, `LC-TWO-SYS V3.1`, **MM32SPIN05PF**, a **split**
  master(主板)+slave(副板) pair.
- Firmware = `trondin/MM32SPIN05_Hoberboard_hack` (EFeru clone, UART only, no FOC).
  Prebuilt `mm32/firmware.hex` is vendored here.
- Flash via **pyOCD** + ST-Link. Protocol = EFeru `0xABCD` — our driver
  `src/forrest/drivers/hoverboard.py` already matches (verified vs trondin structs).

## Confirmed
- Firmware exists for this exact chip; prebuilt hex in `mm32/`.
- Serial protocol matches our driver and `forrest drive listen|spin`.
- Reference pinout (`mm32/pinout.jpg`): SWD = `GND 5V CLK RST DIO`; UART (blue) =
  `GND PB6/Tx PB4/Rx +12V`.

## Open / to verify (do before anything irreversible)
1. **CP2102 loopback** proven on the Mac (`M1`). ← user is here now.
2. **Pinout matches the real LC-TWO-SYS V3.1 silkscreen** (`M2`): SWD pad order,
   UART connector.
3. **Slave (副板) chip is also MM32SPIN05** — needs a close-up.
4. **Exact pyOCD unlock/erase** command for MM32 read-protection (`pyocd erase
   --mass` vs chip-specific) — confirm on the first board, capture output.
5. **Split control**: flashing both halves + commanding each wheel over its own
   UART (chosen). Confirm trondin runs cleanly as independent single-board per
   half (inter-board link unused).

## Rules
- `M3`+ (unlock/flash) erase the stock firmware **permanently**. Keep on human
  approval; do nothing irreversible until items 2–3 above are confirmed.
- Flash with the board on **its own battery**, **holding the power button**.
- **Never** connect the UART `+12V` pin, or anything to the CP2102's 3V3/5V.
- Spin only with **wheels off the ground**; `forrest drive spin` is capped at |150|.

## Repo map
- `README.md` — the step-by-step runbook (M0–M7).
- `mm32/` — vendored `firmware.hex`, `pinout.jpg`, `schematic.jpg` (source: trondin).
- `reference_stm32/` — the STM32/EFeru path we prepared for the G13; reference only.
- `src/forrest/drivers/hoverboard.py` + `tests/test_hoverboard_protocol.py` — the
  serial driver (works as-is).
- `src/forrest/tools/cli.py` — `forrest drive listen|spin`.
