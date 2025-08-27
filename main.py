import library
import playback
import syslog
from volume_control import VolumeControl, cleanup
from threading import Thread, Event
from traceback import format_exc
from nfc_monitor import NFCMonitor

stop_event = Event()

def thread(func):
    try:
        func()
    except:
        e = format_exc()
        print(e)
        syslog.syslog(syslog.LOG_ERR, e)
        stop_event.set()

def handle_new_card(uid_str: str):
    print(f"handling new card: {uid_str}")
    if library.playlists[uid_str]:
        playback.queue(uid_str)

def handle_card_removed():
    print("card removed")
    playback.stop()

try:
    playback.init()
    monitor = NFCMonitor(
        on_card_detected=handle_new_card,
        on_card_removed=handle_card_removed,
    ).start()
    VolumeControl().start()
    

    stop_event.wait()
except Exception as e:
    print(f"Error: {e}")
