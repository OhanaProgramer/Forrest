# Sensor Pico W (RP2040), placeholder firmware: blink the onboard LED.
# Shows the board is powered and running main.py until the I2C sensors
# (INA219 0x40, BME688 0x77, IMU 0x6A) are worked in.
# Pattern: short flash once a second (on 100 ms, off 900 ms).
# On the Pico W the LED is on the CYW43 wireless chip, so it's Pin("LED"), not GP25.
import time
from machine import Pin

led = Pin("LED", Pin.OUT)
print("READY sensors (led-blink placeholder)")

while True:
    led.on()
    time.sleep_ms(100)
    led.off()
    time.sleep_ms(900)
