#!/usr/bin/env python3
"""
NFC Music Player for Raspberry Pi Zero 2W — SPI version with event callbacks
"""

import os
import time
import subprocess
import threading
import signal
import sys
import digitalio
import board
import queue
from csv_watcher import CSVWatcher
from music_player import MusicPlayer
from nfc_monitor import NFCMonitor

MUSIC_PATH = '/home/slooker/music'
CSV_FILE = '/home/slooker/music/music.csv'

def signal_handler(sig, frame):
    print("\nShutting down...")
    sys.exit(0)

def main():
    print("NFC Music Player — SPI Version")
    print("==============================")
    print("Controls:")
    print("  Place NFC card: Play music")
    print("  Remove NFC card: Stop music")
    print("  Volume control: Run volume_control_separate.py separately")
    print()

    watcher = CSVWatcher(CSV_FILE)
    csv_queue = watcher.start()

    player = MusicPlayer(MUSIC_PATH, CSV_FILE)

    # Setup NFC monitor with callbacks
    monitor = NFCMonitor(
        on_card_detected=player.handle_new_card,
        on_card_removed=player.handle_card_removed,
    )
    monitor.start()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    print("Ready to scan cards...")
    print(f"Music directory: {MUSIC_PATH}")

    try:
        while True:
            # Check the queue to see if csv changed
            changed = csv_queue.get()
            if changed:
                if changed == True:
                    player.load_uid_map()

            if player.audio_playing:
                player.check_and_apply_volume_change()
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        monitor.stop()
        player.stop_audio_immediately()


if __name__ == "__main__":
    main()

