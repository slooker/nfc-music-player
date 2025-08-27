#!/usr/bin/env python3
"""
Raw PN532 SPI probe for Raspberry Pi
- Tries CE0 and CE1
- Sends GetFirmwareVersion command (0xD4 0x02)
- Dumps raw SPI bytes
- Flags all-0xFF / all-0x00 responses
"""

import spidev
import time

# PN532 frame constants
PREAMBLE = 0x00
STARTCODE1 = 0x00
STARTCODE2 = 0xFF
POSTAMBLE = 0x00

def build_frame(data):
    """Build a simple PN532 SPI frame (no checksums for minimal probe)"""
    length = len(data)
    lcs = (0x100 - length) & 0xFF
    dcs = (0x100 - sum(data)) & 0xFF
    frame = [PREAMBLE, STARTCODE1, STARTCODE2, length, lcs] + data + [dcs, POSTAMBLE]
    return frame

def probe_ce(bus, device):
    print(f"\nTesting SPI CE{device} (bus {bus}, device {device})...")
    spi = spidev.SpiDev()
    spi.open(bus, device)
    spi.max_speed_hz = 500000
    spi.mode = 0

    # Minimal GetFirmwareVersion command
    # Command: 0xD4 0x02
    cmd = [0xD4, 0x02]
    frame = build_frame(cmd)

    print(f"Sending frame: {frame}")
    resp = spi.xfer2(frame)
    print(f"Received: {resp}")

    if all(b == 0xFF for b in resp):
        print("⚠️  All bytes are 0xFF — no communication. Check wiring, CE, and power.")
    elif all(b == 0x00 for b in resp):
        print("⚠️  All bytes are 0x00 — no communication. Check wiring, CE, and power.")
    else:
        print("✅ Response received! PN532 may be responding. Inspect bytes above.")

    spi.close()

def main():
    print("Starting minimal PN532 SPI raw probe...")
    # Try CE0
    probe_ce(0, 0)
    # Try CE1
    probe_ce(0, 1)
    print("\nProbe complete.")

if __name__ == "__main__":
    main()

