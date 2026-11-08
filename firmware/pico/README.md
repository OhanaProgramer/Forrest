# Pico safety bridge (B4, bench stage)

MicroPython on a Raspberry Pi Pico 2. Sits between the Pi and the drive:

- reads the RC receiver; the transmitter's override switch always wins (to do)
- forwards the Pi's speed/steer commands to the drive (1/10 RC truck ESC + steering servo; future)
- stops the drive if the Pi goes quiet (heartbeat timeout, 500 ms; bench-verified)

## Layout (`drive/`)

One job per module; `main.py` only wires them together.

| File | Job | Tested |
|---|---|---|
| `comm.py` | USB serial: whole lines in, replies out, never blocks | `tests/test_pico_comm.py` |
| `heartbeat.py` | Pi-is-alive watchdog; trips the failsafe | `tests/test_pico_heartbeat.py` |
| `protocol.py` | parse `throttle,steer`; command → pulse width | `tests/test_pico_protocol.py` |
| `main.py` | pins + loop; line protocol documented at the top | on the bench |

New modules follow the same pattern: pure logic with the time passed in (so
pytest can run it), and hardware only in `main.py` or a small class that imports
`machine` when it's created.

## Deploy

```bash
firmware/pico/deploy.sh          # copies all modules + main.py, then resets the board
```

Edit in the repo, deploy, never edit on the board. `mpremote` lives in `.venv`.

Drive wiring rules: to be written when the RC truck is chosen.
