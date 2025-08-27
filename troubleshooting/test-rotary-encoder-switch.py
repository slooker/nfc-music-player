#!/usr/bin/env python3
import RPi.GPIO as GPIO
import time, sys, signal, traceback, os

VOLUME_FILE = '/tmp/music_volume'
volume = 50
min_volume = 0
max_volume = 100
volume_step = 5

CLK_PIN = 16  # pin 36
DT_PIN  = 20  # pin 38
SW_PIN  = 12  # pin 32 (button -> GND, using internal pull-up)

debounce_delay = 0.01
button_delay   = 0.25

muted_volume = None

def setup_gpio():
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    GPIO.setup(CLK_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(DT_PIN,  GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(SW_PIN,  GPIO.IN, pull_up_down=GPIO.PUD_UP)
    print(f"Volume control initialized on GPIO pins CLK={CLK_PIN}, DT={DT_PIN}, SW={SW_PIN}")

def read_volume():
    global volume
    try:
        with open(VOLUME_FILE, 'r') as f:
            volume = int(f.read().strip())
    except Exception as e:
        # Create/reset the file if missing or corrupt
        safe_write_volume()

def safe_write_volume():
    try:
        # Ensure directory exists (it should for /tmp, but harmless)
        os.makedirs(os.path.dirname(VOLUME_FILE), exist_ok=True)
        with open(VOLUME_FILE, 'w') as f:
            f.write(str(volume))
    except Exception as e:
        # Don’t crash on I/O errors—just log them
        print(f"[WARN] Error writing volume file: {e}")

def change_volume(delta):
    global volume, muted_volume

    if muted_volume is not None:
        volume = muted_volume
        muted_volume = None
        print(f"Unmuted - Volume: {volume}%")

    new_volume = max(min_volume, min(max_volume, volume + delta))
    if new_volume != volume:
        volume = new_volume
        safe_write_volume()
        print(f"Volume: {volume}%")

def toggle_mute():
    global volume, muted_volume
    # Wrap everything to avoid crash on press
    try:
        if muted_volume is None:
            if volume > 0:
                muted_volume = volume
                volume = 0
                safe_write_volume()
                print("Muted")
            else:
                print("Already at 0%")
        else:
            volume = muted_volume
            muted_volume = None
            safe_write_volume()
            print(f"Unmuted - Volume: {volume}%")
    except Exception as e:
        print("[ERROR] toggle_mute failed:", repr(e))
        traceback.print_exc()

def cleanup(signum=None, frame=None):
    print("\nCleaning up GPIO...")
    GPIO.cleanup()
    sys.exit(0)

def main():
    print("Volume Control for NFC Music Player")
    print("Rotate encoder to change volume, press button to mute/unmute")
    print("Ctrl+C to exit")

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    setup_gpio()
    read_volume()
    print(f"Current volume: {volume}%")

    last_clk = GPIO.input(CLK_PIN)
    last_sw  = GPIO.input(SW_PIN)
    last_rot_time = time.time()
    last_btn_time = time.time()

    try:
        while True:
            now = time.time()

            # Rotary
            clk = GPIO.input(CLK_PIN)
            if clk != last_clk and (now - last_rot_time) > debounce_delay:
                dt = GPIO.input(DT_PIN)
                if clk == 0:
                    change_volume(volume_step if dt != clk else -volume_step)
                last_rot_time = now
            last_clk = clk

            # Button (active-low to GND)
            sw = GPIO.input(SW_PIN)
            if sw == 0 and last_sw == 1 and (now - last_btn_time) > button_delay:
                try:
                    toggle_mute()
                except Exception as e:
                    print("[ERROR] Button handler crashed:", repr(e))
                    traceback.print_exc()
                last_btn_time = now
            last_sw = sw

            time.sleep(0.001)

    except Exception as e:
        print("Fatal error in main loop:", repr(e))
        traceback.print_exc()
    finally:
        cleanup()

if __name__ == "__main__":
    main()

