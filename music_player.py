import os
import pathlib
import subprocess
import threading
from time import sleep

class MusicPlayer:
    def __init__(self, music_path, csv_file):
        self.music_path = music_path
        self.csv_file = csv_file
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
        self.csv_thread = None
        self.csv_changed_queue = None

    def load_uid_map(self):
        self.uid_map = {}
        try:
            with open(self.csv_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if "," in line and not line.startswith("#"):
                        uid, song = line.split(",", 1)
                        full_path = pathlib.Path(self.music_path) / pathlib.Path(song.strip())
                        #full_path = os.path.join(self.music_path, song.strip())
                        self.uid_map[uid.strip()] = full_path
            print(f"UID map loaded: {len(self.uid_map)} entries")
        except FileNotFoundError:
            print(f"Warning: {self.csv_file} not found. Create this file with UID,filename pairs")

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
                    sleep(0.1)
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
