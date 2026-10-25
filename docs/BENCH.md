# Bench runbook: B1 and B2

The success line for Forrest Jr is the **sensor-and-power module working
stand-alone on a bench**. These are the exact steps. Design reasons live in
Continuity (`02_Projects/Forrest/SYSTEMS.md`, "Jr direction").

## One-time Pi setup

```bash
cd ~                                   # on forrest-jr
git clone https://github.com/OhanaProgramer/Forrest.git forrest
cd forrest
bash pi/setup_pi.sh            # reports what's missing
bash pi/setup_pi.sh --apply    # makes the changes (dialout group, USB current)
sudo reboot
```

After the reboot: `source ~/forrest/.venv/bin/activate`.

## B1: LIDAR on the Pi, wall power

1. Plug the C1 into its USB-C adapter board, the adapter into a Pi USB port.
2. `forrest lidar check`
   - First lines: model, firmware, serial, health. Health should be `good`.
   - Then a live line: scan rate (about 10 Hz), point count, and the nearest
     object in each of 8 sectors.
3. Walk slowly around it about 1 m away. The sector you're in should show
   about 1.0 m and move with you.
4. Record a sample to replay on the Mac:
   `forrest lidar record data/recordings/b1_walkaround.jsonl --seconds 30`
5. Optional, on the Pi desktop: `forrest lidar view` (live polar plot).
   On the Mac with a recording: `forrest lidar view --replay data/recordings/b1_walkaround.jsonl`

**Done when** you can see yourself as a moving blob.

If the port isn't `/dev/ttyUSB0`, `ls /dev/ttyUSB* /dev/ttyACM*` and pass
`--port`.

## B2: same thing on the 3S battery

Wiring: 3S LiPo -> XT60 pigtail -> buck converter input (check polarity:
red +, black -) -> buck USB-C out -> Pi. Low-voltage alarm plugged into the
pack's balance lead. Nothing from the battery goes anywhere else.

1. Boot the Pi **on the battery** (so the since-boot power flags are clean).
2. `forrest soak --minutes 60`
   - Logs temperature and the Pi's power flags every 10 s to `data/soak_*.csv`
     while the LIDAR spins the whole time.
3. Let the alarm be your guard: if it sounds, stop and recharge.

**Done when** the result says `PASS` (no under-voltage) after 60 minutes and
the alarm has been seen to work. That's the Jr success line.

## Safety habits

- ESD mat with its ground cord connected; touch it before handling boards.
- Charge LiPos in the LiPo bag, on a hard surface, while you're home.
- Never run the pack below the alarm. Store packs part-charged, not full.
