import wifi, time
try:
    print("MAC:", [hex(b) for b in wifi.radio.mac_address])
    print("IPv4 (before connect):", wifi.radio.ipv4_address)
    # Comment out connect if you just want to test CYW43 bring-up:
    # wifi.radio.connect("SSID","PASSWORD")
    # print("IPv4 (after):", wifi.radio.ipv4_address)
except Exception as e:
    print("WiFi init error:", repr(e))
while True:
    time.sleep(1)
