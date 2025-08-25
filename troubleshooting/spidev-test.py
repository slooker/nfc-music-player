import spidev

spi = spidev.SpiDev()
spi.open(0,0)
spi.max_speed_hz = 500000
resp = spi.xfer2([0x00])
print(resp)

