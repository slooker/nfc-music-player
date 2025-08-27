import time
import busio
import board
import digitalio
import spidev

# SPI bus setup
spi = spidev.SpiDev()
spi.open(0, 1)  # CE1 / Pin 26 (try 0,0 for CE0 if needed)
spi.max_speed_hz = 1000000  # 1 MHz is safe

# Optional: reset pin
reset_pin = digitalio.DigitalInOut(board.D25)
reset_pin.direction = digitalio.Direction.OUTPUT
reset_pin.value = False
time.sleep(0.1)
reset_pin.value = True
time.sleep(0.1)

print("Starting minimal PN532 SPI probe...")

# This is the PN532 GetFirmwareVersion command frame:
# Preamble: 0x00 0x00 0xFF LEN LCS TF PD0 PD1 … TAIL
# Minimal version for test: just send D4 02 (GetFirmwareVersion)
# Adafruit adds framing, here we just probe raw SPI

try:
    # Send 0x00 0x00 0xFF 0x02 0xFE 0xD4 0x02 0x2A 0x00 (minimal frame)
    write_frame = [0x00, 0x00, 0xFF, 0x02, 0xFE, 0xD4, 0x02, 0x2A, 0x00]
    print("Writing frame:", [hex(b) for b in write_frame])
    recv = spi.xfer2(write_frame)
    print("Received:", [hex(b) for b in recv])

    # Quick check for invalid responses
    if all(b == 0xFF for b in recv):
        print("⚠️ All 0xFF: PN532 not responding, wiring/CE/power issue")
    elif all(b == 0x00 for b in recv):
        print("⚠️ All 0x00: PN532 not powered or not connected")
    else:
        print("⚠️ PN532 may be responding! Check actual firmware response")
except Exception as e:
    print("Error communicating with SPI:", e)
finally:
    spi.close()

