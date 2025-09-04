import time
import board, busio
from digitalio import DigitalInOut, Direction
from adafruit_pn532.spi import PN532_SPI

# --- Wiring (Pico W, SPI1) ---
# SCK  -> GP10 (pin 14)
# MOSI -> GP11 (pin 15)
# MISO -> GP12 (pin 16)
# CS   -> GP8  (pin 11)
# RST  -> GP14 (pin 19)
# 3V3  -> pin 37
# GND  -> pin 39

# Create hardware SPI1
spi = busio.SPI(clock=board.GP10, MOSI=board.GP11, MISO=board.GP12)

# (Optional but recommended) configure SPI speed before using PN532
# Try 1 MHz first; if you still get timeouts, drop to 400_000.
while not spi.try_lock():
    pass
try:
    spi.configure(baudrate=1_000_000, polarity=0, phase=0, bits=8)
finally:
    spi.unlock()

# CS pin
cs = DigitalInOut(board.GP8)

# Hard reset the PN532 (active-low)
rst = DigitalInOut(board.GP14)
rst.direction = Direction.OUTPUT
rst.value = True
time.sleep(0.05)
rst.value = False
time.sleep(0.1)
rst.value = True
time.sleep(0.4)  # allow PN532 to boot

# Create driver (no 'baudrate' kw here)
pn532 = PN532_SPI(spi, cs, reset=rst, debug=True)

# Probe firmware
ic, ver, rev, support = pn532.firmware_version
print(f"Found PN532 {ver}.{rev}")
pn532.SAM_configuration()

print("Touch a tag...")
while True:
    uid = pn532.read_passive_target(timeout=0.5)
    if uid:
        print("UID:", " ".join(f"{b:02X}" for b in uid))
        time.sleep(0.5)
