# Hoverboard drive board: flow of events

Goal: the Gyroor G13's mainboard runs the EFeru FOC firmware and talks serial,
so Forrest can command each wheel and read back speed, battery and temperature.
That data is the **Drive card** (dashboard card 1). Reasons and decisions live
in Continuity (`02_Projects/Forrest/SYSTEMS.md`).

Status: **nothing here has run on hardware yet.** The firmware settings and
the serial driver are written from the EFeru source and wiki (pinned commit in
`prepare.sh`).

## Kit

| Item | Job |
|---|---|
| ST-Link V2 (HiLetgo) | Unlocks the chip and writes the new firmware (installing the app) |
| CP2102 USB-serial adapter | Talks to the firmware while it runs (using the app) |
| USB-C to USB-A adapters | Mac ports |
| Dupont jumpers (female) | ST-Link to the board's 4-pin programming header |
| 2.54 mm male header, soldering iron | If the programming header is bare holes |
| Multimeter | Check the sensor-cable wires before connecting |

## The steps

Each step has a **done when**. Don't start the next one until it's met.
Steps H0 to H2 can be undone; **H3 cannot.**

### H0. Prepare the Mac (now, no board needed)

```bash
cd ~/Projects/.../forrest        # wherever the repo lives on the Mac
bash firmware/hoverboard/mac_setup.sh
bash firmware/hoverboard/prepare.sh
cd firmware/hoverboard/build/efoc && pio run -e VARIANT_USART
```

Also: slide the ST-Link's metal shell off and check the pin names printed on
its circuit board against the label on the shell. Some clones differ; wire by
the board's printing. Photo it.

**Done when** `st-info --probe` sees the ST-Link and the build ends with
`firmware.bin` under `.pio/build/VARIANT_USART/`.

Forrest's settings (applied by `prepare.sh`, listed by its diff):
- serial control on the **left sensor cable** (USART2, 115200 baud)
- **tank steering**: each command sets the left wheel and the right wheel
- bench limits: 5 A per motor, 200 rpm (about 1.7 m/s). Raised later.
- 10-cell (36 V) battery, the firmware default. Change `BAT_CELLS` if the label disagrees.

### H1. Arrival check (returnable)

1. Label: expect **36 V, 72 Wh** (2 Ah). Photo it.
2. Ride-test it stock for a minute: both wheels drive, no error beeps. A dead board is a return, not a project.
3. Open it. Photo the whole board, then close-ups.

**Done when** the photos answer:
- One **mainboard** in the middle plus two **sideboards** (gyro boards)? Or a split design like the HY-A02C?
- Chip marking: **STM32F103RCT6** or **GD32F103RCT6** (64 pins). Anything else, stop.
- A 4-pin header or pads next to the chip (GND, 3V3, SWDIO, SWCLK).
- The two sensor-cable connectors (left = long cable, right = short).

### H2. Keep-or-return decision

If H1 passes, this is the board. Ship the HY-A02C back.
If it fails, return the G13 and we look again.

### Staying recoverable (read once before H3)

The chip can always be wiped and reflashed through SWDIO/SWCLK; a failed or
interrupted flash means "flash again". What actually kills boards:
- powering the board from the ST-Link's 3.3V pin (never connected here);
- the sensor cable's ~15 V wire reaching a data pin (multimeter first, red wire unused);
- shorts while wiring (battery off while connecting);
- a chip other than STM32F103 / GD32F103 (H1 checks).
If a GD32 acts oddly after flashing, the unlock didn't fully clear: redo it with
the EFeru wiki's longer command set, then flash again.

### H3. Unlock (one-way: erases the stock firmware forever)

The original firmware can't be read out or restored. After this the board is
Forrest's, not a hoverboard.

First, try a backup anyway (harmless, takes seconds, wiring as below):

```bash
st-info --probe                                   # chip ID and flash size; works even when locked
st-flash read stock_backup.bin 0x8000000 0x40000  # 256 KB
```

Expected: the read fails or the file is all zeros/0xFF, which confirms the
chip's read protection is on and there's nothing to save. If it ever comes back
with real data, keep that file and tell me before unlocking.

Wiring, ST-Link to the board header:

| ST-Link | Board |
|---|---|
| GND | GND |
| SWDIO | SWDIO |
| SWCLK | SWCLK |
| 3.3V | **leave unconnected** |

The board runs on **its own battery** while you do this, and you **hold the
power button** the whole time (the chip otherwise releases its power latch and
switches itself off).

```bash
openocd -f interface/stlink.cfg -f target/stm32f1x.cfg -c init -c "reset halt" -c "stm32f1x unlock 0" -c shutdown
```

Then power-cycle the board (still holding the button to turn it on).
**Done when** `st-info --probe` shows the chip with its flash size.
If unlock fails, the EFeru wiki "How to Unlock MCU Flash" has the longer
command set; send me the output first.

### H4. Flash

Same wiring, battery on, hold the power button:

```bash
cd firmware/hoverboard/build/efoc
pio run -e VARIANT_USART -t upload
# or: st-flash --reset write .pio/build/VARIANT_USART/firmware.bin 0x8000000
```

**Done when** the upload says it verified, and the board beeps on power-up
with the new firmware. With no commands arriving it beeps a warning after
about 0.8 s; that is the serial timeout, and it's what we want.

### H5. Serial link (wheels off the ground)

Board upside down or wheels on blocks from here on.

1. Unplug the **left sideboard's** cable from the mainboard. That cable is now ours.
2. Multimeter on the mainboard's left connector, board on: find which wire is
   ground and which carries about **15 V** (red, usually). Some boards swap them.
3. CP2102 to the cable:

| Cable wire | CP2102 |
|---|---|
| Black (GND, after checking) | GND |
| Green (board TX) | RXD |
| Blue (board RX) | TXD |
| Red (15 V) | **nothing** |

   Nothing on the CP2102's 3.3V or 5V pins. If no data, swap green and blue.

4. On the Mac:

```bash
forrest drive listen --port /dev/cu.usbserial-XXXX
```

**Done when** it prints about 100 frames a second: battery volts near the
pack's real voltage, board temperature, both wheel speeds 0.
Check the voltage against the multimeter; if it's off by more than ~0.5 V we
calibrate (`BAT_CALIB_*` in config.h) and re-flash.

### H6. First spin

```bash
forrest drive spin --port /dev/cu.usbserial-XXXX --left 50 --right 50 --seconds 3
```

`50` is 5% of full command. The tool sends commands 20 times a second and
prints the measured rpm. Releasing (or Ctrl-C) stops the stream, and the board
stops the wheels by itself within 0.8 s.

**Done when** each wheel turns, in the expected direction, and its rpm shows up
in the feedback. Try `--left 50 --right 0` and the reverse to confirm which is
which. Wrong direction or rough running: send me the output (phase or hall
mapping, per the EFeru troubleshooting list).

### H7. Drive card

The same feedback goes to the one log and onto dashboard card 1.
Later, the Pico takes the CP2102's place (B4).
