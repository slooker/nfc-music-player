#!/usr/bin/env python3
import board
import busio
from digitalio import DigitalInOut
from adafruit_pn532.spi import PN532_SPI

# SPI setup
spi = busio.SPI(clock=board.SCK, MOSI=board.MOSI, MISO=board.MISO)
#cs_pin = DigitalInOut(board.D7)  # CE1 / GPIO7 -> physical pin 26
cs_pin = DigitalInOut(board.CE1)

# Initialize PN532 over SPI
pn532 = PN532_SPI(spi, cs_pin, debug=False)

try:
    ic, ver, rev, support = pn532.firmware_version
    print(f"PN532 detected! Chip PN5{ic:02X} Firmware Version: {ver}.{rev}")
except Exception as e:
    print(f"Failed to detect PN532: {e}")

