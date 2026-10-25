# Pico safety bridge (B4, not started)

MicroPython on a Raspberry Pi Pico 2. Sits between the Pi and the drive:

- reads the RC receiver; the transmitter's override switch always wins
- forwards the Pi's speed/steer commands to the hoverboard board over UART
- stops the drive if the Pi goes quiet (heartbeat timeout)

Wiring rule for the hoverboard link: GND, TX, RX only. The same connector
carries about 15 V on one pin; it must never reach the Pico.
