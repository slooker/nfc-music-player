import spidev
import time

print("Starting SPI low-level test...")

# Try both CE0 and CE1
for bus, device, pin_name in [(0, 0, "CE0 / Pin 24 / GPIO8"), (0, 1, "CE1 / Pin 26 / GPIO7")]:
    print(f"\nTesting SPI bus 0, device {device} ({pin_name})...")
    try:
        spi = spidev.SpiDev()
        spi.open(bus, device)
        spi.max_speed_hz = 500000
        spi.mode = 0b00

        # Send some dummy bytes
        resp = spi.xfer2([0xAA, 0x55, 0x00, 0xFF])
        print(f"Sent [0xAA,0x55,0x00,0xFF], received: {resp}")

        # Check for all 255
        if all(b == 0xFF for b in resp):
            print(f"⚠️  Received all 0xFF. Likely no device or wiring problem on {pin_name}")
        else:
            print(f"✅ SPI communication works on {pin_name}")

        spi.close()
    except FileNotFoundError:
        print(f"⚠️ SPI device {pin_name} not found. Is SPI enabled in raspi-config?")
    except Exception as e:
        print(f"⚠️ Error on {pin_name}: {e}")

print("\nSPI test complete.")

