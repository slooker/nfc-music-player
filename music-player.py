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
import pathlib
import queue
from adafruit_pn532.spi import PN532_SPI


BASE_PATH = '/home/slooker/music'
CSV_FILE = '/home/slooker/music/music.csv'


class CSVWatcher:
    def __init__(self):
        self.last_modified_csv_time = 0
        self.stop_event = threading.Event()
        self.csv_thread = None
        self.csv_changed_queue = queue.Queue()

    def _watch_csv_loop(self):
        """Thread loop that checks for CSV changes every 10 seconds"""
        while not self.stop_event.is_set():
            try:
                current_modified_time = os.path.getmtime(CSV_FILE)
                if current_modified_time != self.last_modified_csv_time:
                    print("CSV is changed!")
                    self.last_modified_csv_time = current_modified_time
                    self.csv_changed_queue.put(True)
                else:
                    print("CSV is not changed")
                    self.csv_changed_queue.put(False)
            except FileNotFoundError:
                print("CSV file not found!")
            # Sleep in small increments so we can exit quickly
            for _ in range(10):
                if self.stop_event.is_set():
                    break
                time.sleep(1)

        print("CSV watcher thread stopping...")

    def start(self):
        if self.csv_thread is None or not self.csv_thread.is_alive():
            print("Starting CSV watcher thread")
            self.csv_thread = threading.Thread(target=self._watch_csv_loop, daemon=True)
            self.csv_thread.start()
        return self.csv_changed_queue

    def stop(self):
        print("Stopping CSV watcher thread...")
        self.stop_event.set()
        if self.csv_thread:
            self.csv_thread.join()
        print("CSV watcher stopped.")

class NFCMonitor:
    def __init__(self, pn532, on_card_detected, on_card_removed):
        self.pn532 = pn532
        self.on_card_detected = on_card_detected
        self.on_card_removed = on_card_removed

        self.thread = None
        self.stop_flag = threading.Event()

        self.last_uid = None
        self.card_present = False
        self.no_card_count = 0
        self.no_card_threshold = 3  # consecutive misses before removal

    def monitor_loop(self):
        while not self.stop_flag.is_set():
            try:
                uid = self.pn532.read_passive_target(timeout=0.1)
                if uid:
                    uid_str = "".join("{:02X}".format(b) for b in uid)
                    if not self.card_present:
                        self.card_present = True
                        self.last_uid = uid_str
                        self.no_card_count = 0
                        self.on_card_detected(uid_str)
                    elif uid_str != self.last_uid:
                        self.last_uid = uid_str
                        self.on_card_detected(uid_str)
                    else:
                        self.no_card_count = 0
                else:
                    if self.card_present:
                        self.no_card_count += 1
                        if self.no_card_count >= self.no_card_threshold:
                            self.card_present = False
                            self.last_uid = None
                            self.no_card_count = 0
                            self.on_card_removed()
                    else:
                        self.no_card_count = 0

                if self.card_present:
                    time.sleep(0.3)
                else:
                    time.sleep(0.1)
            except Exception as e:
                print(f"❌ NFC polling error: {e}")
                time.sleep(1)

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        self.stop_flag.clear()
        self.thread = threading.Thread(target=self.monitor_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_flag.set()
        if self.thread:
            self.thread.join()


class MusicPlayer:
    def __init__(self):
        self.last_uid = None
        self.audio_playing = False
        self.current_process = None
        self.should_stop_audio = threading.Event()
        self.uid_map = {}
        self.load_uid_map()
        self.volume = 50
        self.min_volume = 0
        self.max_volume = 100
        self.volume_file = '/tmp/music_volume'
        self.has_software_volume = False
        self.setup_initial_volume()
        self.last_modified_csv_time = os.path.getmtime(CSV_FILE)
        self.csv_thread = None
        self.csv_changed_queue = None

    def load_uid_map(self):
        self.uid_map = {}
        try:
            with open(CSV_FILE, 'r') as f:
                for line in f:
                    line = line.strip()
                    if "," in line and not line.startswith("#"):
                        uid, song = line.split(",", 1)
                        full_path = pathlib.Path(BASE_PATH) / pathlib.Path(song.strip())
                        #full_path = os.path.join(BASE_PATH, song.strip())
                        self.uid_map[uid.strip()] = full_path
            print(f"UID map loaded: {len(self.uid_map)} entries")
        except FileNotFoundError:
            print(f"Warning: {CSV_FILE} not found. Create this file with UID,filename pairs")

    def setup_initial_volume(self):
        try:
            result = subprocess.run(['amixer', '-c', '0', 'sget', 'SoftMaster'],
                                    capture_output=True, text=True)
            if result.returncode == 0:
                subprocess.run(['amixer', '-c', '0', 'sset', 'SoftMaster', f'{self.volume}%'],
                               capture_output=True)
                print(f"Software volume control ready: {self.volume}%")
                self.has_software_volume = True
            else:
                print("SoftMaster control not found. See setup instructions for .asoundrc")
                self.has_software_volume = False

            with open(self.volume_file, 'w') as f:
                f.write(str(self.volume))
        except Exception as e:
            print(f"Warning: Could not setup software volume control: {e}")
            self.has_software_volume = False

    def check_and_apply_volume_change(self):
        try:
            if os.path.exists(self.volume_file):
                with open(self.volume_file, 'r') as f:
                    new_volume = int(f.read().strip())
                if new_volume != self.volume:
                    old_volume = self.volume
                    self.volume = max(self.min_volume, min(self.max_volume, new_volume))
                    if self.has_software_volume:
                        subprocess.run(['amixer', '-c', '0', 'sset', 'SoftMaster', f'{self.volume}%'],
                                       capture_output=True, check=True)
                    print(f"🔊 Volume: {old_volume}% → {self.volume}%")
                    return True
            else:
                with open(self.volume_file, 'w') as f:
                    f.write(str(self.volume))
        except Exception:
            pass
        return False

    def stop_audio_immediately(self):
        print("🛑 Stopping audio immediately...")
        self.should_stop_audio.set()
        self.audio_playing = False
        if self.current_process:
            try:
                self.current_process.kill()
                self.current_process.wait(timeout=1)
            except Exception:
                pass
            self.current_process = None
        subprocess.run(['sudo', 'pkill', '-9', 'mpg123'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("🛑 Audio stopped")

    def play_single_file(self, filepath):
        try:
            self.check_and_apply_volume_change()
            self.current_process = subprocess.Popen(['mpg123', '-q', '-a', 'default', filepath],
                                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.audio_playing = True
            print(f"▶️ Started playing: {os.path.basename(filepath)} at {self.volume}%")
        except Exception as e:
            print(f"⚠️ Error playing file: {e}")
            self.audio_playing = False

    def play_folder(self, folder_path):
        try:
            mp3_files = sorted(
                [os.path.join(folder_path, f) for f in os.listdir(folder_path) if f.lower().endswith('.mp3')]
            )
            if not mp3_files:
                print(f"⚠️ No MP3 files found in {folder_path}")
                return
            print(f"🎵 Playing {len(mp3_files)} files from folder: {os.path.basename(folder_path)}")
            self.check_and_apply_volume_change()
            self.audio_playing = True
            for mp3_file in mp3_files:
                if self.should_stop_audio.is_set():
                    break
                print(f"🎵 Playing: {os.path.basename(mp3_file)}")
                self.current_process = subprocess.Popen(
                    ['mpg123', '-q', '-a', 'default', mp3_file],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE
                )
                while True:
                    if self.current_process is None:
                        break
                    retcode = self.current_process.poll()
                    if retcode is not None:
                        self.current_process = None
                        break
                    if self.should_stop_audio.is_set():
                        try:
                            self.current_process.kill()
                        except Exception:
                            pass
                        self.current_process = None
                        break
                    time.sleep(0.1)
            print("✅ Playlist complete")
            self.audio_playing = False
        except Exception as e:
            print(f"⚠️ Error playing folder: {e}")
        finally:
            if self.current_process is not None:
                try:
                    self.current_process.kill()
                except Exception:
                    pass
                self.current_process = None
            self.audio_playing = False
    

    def handle_new_card(self, uid_str):
        if uid_str in self.uid_map:
            file_to_play = self.uid_map[uid_str]
            print(f"🎯 Starting playback for: {uid_str} -> {file_to_play}")
            if os.path.exists(file_to_play):
                if os.path.isfile(file_to_play):
                    self.stop_audio_immediately()
                    self.should_stop_audio.clear()
                    self.play_single_file(file_to_play)
                elif os.path.isdir(file_to_play):
                    self.stop_audio_immediately()
                    self.should_stop_audio.clear()
                    threading.Thread(target=self.play_folder, args=(file_to_play,), daemon=True).start()
            else:
                print(f"⚠️ File not found: {file_to_play}")
        else:
            print(f"❓ UID {uid_str} not found in mapping file")

    def handle_card_removed(self):
        print("🛑 Card removed, stopping playback")
        self.stop_audio_immediately()

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

    watcher = CSVWatcher()
    csv_queue = watcher.start()

    # Initialize PN532 SPI
    spi = board.SPI()
    cs = digitalio.DigitalInOut(board.D7)  # GPIO8 CE0, physical pin 24
    pn532 = PN532_SPI(spi, cs, reset=None, debug=False)
    try:
        ic, ver, rev, support = pn532.firmware_version
        print(f"PN532 initialized: PN5{ic:02x} Firmware {ver}.{rev}")
    except Exception as e:
        print(f"Failed to initialize PN532: {e}")
        sys.exit(1)
    pn532.SAM_configuration()

    player = MusicPlayer()

    # Setup NFC monitor with callbacks
    monitor = NFCMonitor(
        pn532,
        on_card_detected=player.handle_new_card,
        on_card_removed=player.handle_card_removed,
    )
    monitor.start()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    print("Ready to scan cards...")
    print(f"Music directory: {BASE_PATH}")

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

