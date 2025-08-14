#!/usr/bin/env python3
"""
Separate Volume Control Script
Controls volume for NFC Music Player via file communication
Uses RPi.GPIO directly without conflicts
"""

import RPi.GPIO as GPIO
import time
import sys
import signal

# Volume control settings
VOLUME_FILE = '/tmp/music_volume'
volume = 50  # Starting volume
min_volume = 0
max_volume = 100
volume_step = 5

# GPIO pins (same as before)
CLK_PIN = 16  # GPIO 16 (Pin 36)
DT_PIN = 20   # GPIO 20 (Pin 38) 
SW_PIN = 12   # GPIO 12 (Pin 32)

def setup_gpio():
    """Initialize GPIO pins"""
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    
    # Set up rotary encoder pins
    GPIO.setup(CLK_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(DT_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(SW_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    
    print(f"Volume control initialized on GPIO pins {CLK_PIN}, {DT_PIN}, {SW_PIN}")

def read_volume():
    """Read current volume from file"""
    global volume
    try:
        with open(VOLUME_FILE, 'r') as f:
            volume = int(f.read().strip())
    except (FileNotFoundError, ValueError):
        # Create file with default volume
        write_volume()

def write_volume():
    """Write current volume to file"""
    try:
        with open(VOLUME_FILE, 'w') as f:
            f.write(str(volume))
    except Exception as e:
        print(f"Error writing volume: {e}")

def change_volume(delta):
    """Change volume by delta amount"""
    global volume
    new_volume = max(min_volume, min(max_volume, volume + delta))
    
    if new_volume != volume:
        volume = new_volume
        write_volume()
        print(f"🔊 Volume: {volume}%")

def toggle_mute():
    """Toggle mute/unmute"""
    global volume, previous_volume
    
    if volume > 0:
        previous_volume = volume
        volume = 0
        write_volume()
        print("🔇 Muted")
    else:
        volume = getattr(toggle_mute, 'previous_volume', 50)
        write_volume()
        print(f"🔊 Unmuted - Volume: {volume}%")

def rotary_callback(channel):
    """Handle rotary encoder rotation"""
    try:
        clk_state = GPIO.input(CLK_PIN)
        dt_state = GPIO.input(DT_PIN)
        
        if clk_state == 0:  # Falling edge
            if dt_state != clk_state:
                # Clockwise rotation - increase volume
                change_volume(volume_step)
            else:
                # Counter-clockwise rotation - decrease volume
                change_volume(-volume_step)
                
    except Exception as e:
        print(f"Rotary callback error: {e}")

def button_callback(channel):
    """Handle button press"""
    try:
        toggle_mute()
    except Exception as e:
        print(f"Button callback error: {e}")

def cleanup(signum=None, frame=None):
    """Clean up GPIO on exit"""
    print("\nCleaning up GPIO...")
    GPIO.cleanup()
    sys.exit(0)

def main():
    """Main function"""
    print("Volume Control for NFC Music Player")
    print("==================================")
    print("Controls:")
    print("  Rotate: Change volume")
    print("  Press: Toggle mute/unmute")
    print("  Ctrl+C: Exit")
    print()
    
    # Setup signal handlers
    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)
    
    # Initialize GPIO
    setup_gpio()
    
    # Read initial volume
    read_volume()
    print(f"Current volume: {volume}%")
    
    # Variables for polling approach
    last_clk_state = GPIO.input(CLK_PIN)
    last_sw_state = GPIO.input(SW_PIN)
    last_button_time = 0
    last_rotation_time = 0
    debounce_delay = 0.01  # 10ms debounce
    
    try:
        print("Monitoring rotary encoder...")
        
        while True:
            current_time = time.time()
            
            # Check rotation
            clk_state = GPIO.input(CLK_PIN)
            if clk_state != last_clk_state and current_time - last_rotation_time > debounce_delay:
                if clk_state == 0:  # Falling edge
                    dt_state = GPIO.input(DT_PIN)
                    if dt_state != clk_state:
                        # Clockwise rotation - increase volume
                        change_volume(volume_step)
                    else:
                        # Counter-clockwise rotation - decrease volume
                        change_volume(-volume_step)
                
                last_rotation_time = current_time
            last_clk_state = clk_state
            
            # Check button press
            sw_state = GPIO.input(SW_PIN)
            if sw_state == 0 and last_sw_state == 1 and current_time - last_button_time > 0.3:
                toggle_mute()
                last_button_time = current_time
            last_sw_state = sw_state
            
            time.sleep(0.001)  # 1ms polling
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        cleanup()

if __name__ == "__main__":
    main()
