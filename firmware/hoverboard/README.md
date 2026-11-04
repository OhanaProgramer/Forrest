# Hoverboard drive board — flow of events (MM32SPIN05 path)

Goal: Jr's hoverboard mainboard(s) run open firmware and talk serial, so Forrest
can command each wheel and read back speed, battery and temperature. That data is
the **Drive card** (dashboard card 1). Decisions live in Continuity
(`02_Projects/Forrest/SYSTEMS.md`).

**Board:** HY-A02C hoverboard, `LC-TWO-SYS V3.1`, chip **MM32SPIN05PF** (ARM
Cortex-M0, 32 KB). It is a **split design**: a **master (主板)** board with the
MCU + Bluetooth drives one wheel, a **slave (副板)** board drives the other, and
they link over an inter-board cable. (The Gyroor G13 we first tried was not
hackable — chip YY3061, in no open project — and was returned. See Continuity.)

**Firmware:** `trondin/MM32SPIN05_Hoberboard_hack` — an EFeru-clone port for this
exact chip. UART control only, no FOC (the 32 KB flash can't fit it). A prebuilt
`firmware.hex` is vendored in `mm32/` so **first bring-up needs no compiler**.

**Protocol:** EFeru `hoverserial` — start frame `0xABCD`, 115200 8N1, 18-byte
feedback, 8-byte command, XOR checksum. Our driver
(`src/forrest/drivers/hoverboard.py`) already matches it, confirmed against the
trondin structs. `forrest drive listen|spin` work unchanged.

**Flash tool:** **pyOCD** (`pyocd flash -t mm32spin05pf firmware.hex`), driven by
the HiLetgo ST-Link. Not st-flash/openocd — those don't target MM32.

Status: **nothing here has run on this hardware yet.** Pins below are read from
the trondin reference board (`mm32/pinout.jpg`); verify them against the actual
`LC-TWO-SYS V3.1` silkscreen before connecting (see M2).

## Kit
| Item | Job |
|---|---|
| ST-Link V2 (HiLetgo) | Erase + flash the chip via SWD (pyOCD) |
| CP2102 USB-TTL | Talk to the firmware over UART (listen / command) |
| Dupont jumpers (female) | ST-Link → SWD pads; CP2102 → UART connector |
| Multimeter | Verify GND / power pins before connecting |
| USB-C data adapter | Mac port (the one that enumerated the ST-Link, not a charge-only one) |

## Pins (from `mm32/pinout.jpg` — VERIFY on the real board, M2)
- **SWD programming pads:** `GND · 5V · CLK · RST · DIO`.
  ST-Link uses **GND→GND, CLK→SWCLK, DIO→SWDIO**. **Leave 5V off** — the board
  runs on its own battery while flashing. RST optional.
- **UART control (blue 4-pin connector):** `GND · PB6 Tx · PB4 Rx · +12V`.
  CP2102 uses **GND→GND, PB6(Tx)→CP2102 RX, PB4(Rx)→CP2102 TX**.
  **Never connect the +12V pin** to the CP2102 (and nothing on CP2102 3V3/5V).

## Split-board plan (decision)
Flash **both** halves with this firmware; command **each wheel over its own
UART** (two serial lines; the Pico drives both later). Simple and robust — each
wheel is its own controlled motor. The master/slave inter-board link is left
unused for now. (Alternative: a master/slave relay over the inter-board cable —
more integrated, more fiddly; not chosen.)

## The steps

Each has a **done when**. `M3`+ (unlock/flash) are **irreversible** — the stock
hoverboard firmware is erased and cannot be restored. Keep those on human
approval.

### M0. Mac tools (no board)
```bash
brew install stlink            # st-info (probe) — optional but handy
pipx install pyocd || pip install --user pyocd
pyocd pack install mm32spin05pf   # CMSIS pack for the target (if prompted)
st-info --probe                # ST-Link seen? (plug it in, nothing on its pins)
```
Slide the ST-Link's shell off and wire by the pin names printed on its *board*,
not the shell (clones differ).
**Done when** `st-info --probe` sees the ST-Link and `pyocd list` runs.

### M1. Prove the CP2102 (loopback, no board)  ✅ done 2026-11-02
1. Plug CP2102 into the Mac. `ls /dev/cu.*` → expect `/dev/cu.usbserial-0001`.
2. Jumper **TXD↔RXD** on the adapter.
3. `screen /dev/cu.usbserial-0001 115200` — type; characters echo = good. Pull the
   jumper and they stop. Exit screen: Ctrl-A, K, y.
**Done when** the loopback echoes.
Result 2026-11-02: 3 runs × 83 random bytes over `/dev/cu.usbserial-0001` @115200, 83/83 back, exact match each run.

### M2. Hardware ID + bench test — METER ONLY, no computer yet  ← current step
Everything here uses the multimeter on **both** boards (master 主板 + slave 副板)
**before** any ST-Link or CP2102 touches them. Goal: know every pin and prove the
board is electrically sound, so the computer attach (M3) is safe. Record each pin
on the board-map artifact as you go.

Meter setup: black probe → **COM**, red probe → **VΩ** jack. Continuity for ID,
DC volts for the live checks.

**A. Identify the key pins on each board** (compare to `mm32/pinout.jpg`, but
confirm by meter — don't trust silkscreen alone):
- **SWD pads** (`GND 5V CLK RST DIO`): confirm **GND** by continuity to
  battery-negative. These are the flash pins; we use GND / CLK / DIO.
- **UART connector** (blue 4-pin): find **GND** (continuity, power OFF), then the
  **+12V/power** pin (DC volts, power ON — reads ~pack voltage). The remaining two
  are **Tx/Rx**. Write the pin order down.
- **MCU**: confirm each board's center chip is **MM32SPIN05PF** (close-up).
- Note for the map: hall connector, LEDs, button, charge, phase outputs, the
  inter-board link.

**B. Unpowered sanity** (continuity, board OFF):
- All the connector grounds tie to battery-negative.
- **No dead short** battery+ ↔ battery− (should NOT beep).
- Each of the 3 fat phase wires has continuity into the motor (phase-to-phase a
  few ohms; none shorted to ground).

**C. Powered rails** (DC volts, board ON):
- Pack voltage at the battery terminals (~16–18 V on this 18 V board).
- The UART **+12V** pin ≈ pack voltage.
- The **3.3V** pad ≈ 3.3 V (the MCU supply is alive).
- Board powers up to a normal status light (level, no error).

**Done when** both boards are confirmed MM32SPIN05; SWD (GND/CLK/DIO) and UART
(GND/Tx/Rx/+12V) pins are identified and written down; no shorts; 3.3 V and pack
rails good. **Only then → M3** (first computer attach).

### M3. Wire ST-Link → SWD  (board on its OWN battery, hold the power button)
GND→GND, CLK→SWCLK, DIO→SWDIO. 5V unconnected. Hold the power button the whole
time (the chip drops its power latch otherwise).
```bash
pyocd list                     # ST-Link + target visible
```

### M4. Unlock + flash  (irreversible; do for BOTH boards)
```bash
# erase (clears read-protection / stock firmware)
pyocd erase -t mm32spin05pf --mass
# flash the vendored firmware
pyocd flash -t mm32spin05pf firmware/hoverboard/mm32/firmware.hex
```
VERIFY the exact pyOCD unlock command for MM32 read-protection on the first board,
and capture the output. Repeat for the second board.
**Done when** the flash verifies and the board powers up on the new firmware
(with no commands it beeps/stops after ~0.8 s — the serial timeout, expected).

### M5. UART listen  (wheels off the ground)
CP2102 to the blue UART connector: GND→GND, board **Tx→CP2102 RX**, board
**Rx→CP2102 TX**, **+12V unconnected**.
```bash
forrest drive listen --port /dev/cu.usbserial-0001
```
**Done when** it prints ~100 frames/s: battery volts near the pack's real
voltage, board temp, wheel speeds 0. If no data, swap Tx/Rx.

### M6. First spin  (wheels off the ground)
```bash
forrest drive spin --port /dev/cu.usbserial-0001 --left 50 --right 50 --seconds 3
```
`50` = 5% command; `spin` is capped at |150| by default. Prebuilt firmware keeps
stock ceilings (15 A, 1000 rpm), so keep commands gentle; rebuild with lower
limits later via `make` (needs `arm-none-eabi-gcc`).
**Done when** each wheel turns the expected way and its rpm shows in the feedback.
Try `--left 50 --right 0` and the reverse to learn which field is which wheel.

### M7. Drive card
Feed the same frames to the one log and dashboard card 1. Later the Pico replaces
the CP2102 and drives both boards' UARTs (B4).

## Sources
- Firmware + pinout: https://github.com/trondin/MM32SPIN05_Hoberboard_hack
- Board ID / Gen2 family: https://github.com/RoboDurden/Hoverboard-Firmware-Hack-Gen2.x
- Protocol origin: https://github.com/EFeru/hoverboard-firmware-hack-FOC
