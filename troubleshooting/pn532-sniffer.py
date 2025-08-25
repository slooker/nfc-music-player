#!/usr/bin/env python3
import spidev
import time

# CE pins info
CE_PINS = [
    {"bus": 0, "device": 0, "name": "CE0 / Pin 24 / GPIO8"},
    {"bus": 0, "device": 1, "name": "CE1 / Pin 26 / GPIO7"},
]

def check_spi(bus, device, name):
    print(f"\nTesting SPI {name} (bus {bus}, device {device})...")
    try:
        spi = spidev.SpiDev()
        spi.open(bus, device)
        spi.max_speed_hz = 500000
        spi.mode = 0b00

        # Send dummy bytes to see if anything responds
        dummy_bytes = [0x00, 0x00, 0xFF, 0x00]
        response = spi.xfer2(dummy_bytes)
        print(f"Sent: {dummy_bytes}")
        print(f"Received: {response}")

        # Detect if all bytes are 0xFF or 0x00 (no device or bad wiring)
        if all(b == 0xFF for b in response):
            print(f"⚠️ No communication (all 0xFF). Check wiring, CE pin, and power!")
            result = False
        elif all(b == 0x00 for b in response):
            print(f"⚠️ No communication (all 0x00). Check wiring, CE pin, and power!")
            result = False
        else:
            print(f"✅ SPI detected on {name}")
            result = True

        spi.close()
        return result
    except FileNotFoundError:
        print(f"⚠️ SPI device {name} not found. Is SPI enabled in raspi-config?")
        return False
    except Exception as e:
        print(f"⚠️ Error testing {name}: {e}")
        return False

def main():
    print("Starting PN532 SPI detection test...")
    detected = False
    for ce in CE_PINS:
        if check_spi(ce["bus"], ce["device"], ce["name"]):
            detected = True

    if not detected:
        print("\n⚠️ PN532 not detected on either CE0 or CE1.")
        print(" - Check the wiring carefully.")
        print(" - Make sure 3.3V VCC is used (not 5V).")
        print(" - Verify CE pin matches your wiring (CE0 or CE1).")
        print(" - Ensure SPI is enabled on the Pi: sudo raspi-config → Interface Options → SPI")
    else:
        print("\n✅ PN532 detected on at least one CE pin!")

if __name__ == "__main__":
    main()

