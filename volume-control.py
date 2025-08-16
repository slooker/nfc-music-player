#!/usr/bin/env python3
"""
Volume Control for NFC Music Player
Polling-based version for rotary encoder and button
"""

import RPi.GPIO as GPIO
import time
import sys
import signal

# Volume control file
VOLUME_FILE = '/tmp/music_volume'

# Starting volume
volume = 50
min_volume = 0
max_volume = 100
volume_step = 5

# BCM GPIO pins
CLK_PIN = 21  # Pin 40
DT_PIN  = 20  # Pin 38
SW_PIN  = 12  # Pin 32

# Debounce settings
debounce_delay = 0.01  # 10ms for rotary
button_delay = 0.3     # 300ms for button

def setup_gpio():
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    GPIO.setup(CLK_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(DT_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(SW_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    print(f"Volume control initialized on GPIO pins CLK={CLK_PIN}, DT={DT_PIN}, SW={SW_PIN}")

def read_volume():
    global volume
    try:
        with open(VOLUME_FILE, 'r') as f:
            volume = int(f.read().strip())
    except (FileNotFoundError, ValueError):
        write_volume()  # create file with default volume

def write_volume():
    try:
        with open(VOLUME_FILE, 'w') as f:
            f.write(str(volume))
    except Exception as e:
        print(f"Error writing volume: {e}")

def change_volume(delta):
    global volume
    new_volume = max(min_volume, min(max_volume, volume + delta))
    if new_volume != volume:
        volume = new_volume
        write_volume()
        print(f"🔊 Volume: {volume}%")

def toggle_mute():
    global volume
    previous_volume = getattr(toggle_mute, 'previous_volume', 50)
    if volume > 0:
        toggle_mute.previous_volume = volume
        volume = 0
        write_volume()
        print("🔇 Muted")
    else:
        volume = previous_volume
        write_volume()
        print(f"🔊 Unmuted - Volume: {volume}%")

def cleanup(signum=None, frame=None):
    print("\nCleaning up GPIO...")
    GPIO.cleanup()
    sys.exit(0)

def main():
    print("Volume Control for NFC Music Player")
    print("Rotate encoder to change volume, press button to mute/unmute")
    
    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    setup_gpio()
    read_volume()
    print(f"Current volume: {volume}%")

    last_clk = GPIO.input(CLK_PIN)
    last_sw  = GPIO.input(SW_PIN)
    last_rot_time = time.time()
    last_btn_time = time.time()

    while True:
        now = time.time()

        # --- Rotary encoder ---
        clk = GPIO.input(CLK_PIN)
        if clk != last_clk and now - last_rot_time > debounce_delay:
            dt = GPIO.input(DT_PIN)
            if clk == 0:  # falling edge
                if dt != clk:
                    change_volume(volume_step)   # clockwise
                else:
                    change_volume(-volume_step)  # counter-clockwise
            last_rot_time = now
        last_clk = clk

        # --- Button press ---
        sw = GPIO.input(SW_PIN)
        if sw == 0 and last_sw == 1 and now - last_btn_time > button_delay:
            toggle_mute()
            last_btn_time = now
        last_sw = sw

        time.sleep(0.001)  # 1ms polling

if __name__ == "__main__":
    main()

