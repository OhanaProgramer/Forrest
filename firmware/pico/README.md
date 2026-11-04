# Pico safety bridge (B4, not started)

MicroPython on a Raspberry Pi Pico 2. Sits between the Pi and the drive:

- reads the RC receiver; the transmitter's override switch always wins
- forwards the Pi's speed/steer commands to the drive (1/10 RC truck ESC + steering servo; future)
- stops the drive if the Pi goes quiet (heartbeat timeout)

Drive wiring rules: to be written when the RC truck is chosen.
