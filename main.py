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

def handle_new_card(uid_str: str, album_id: str | None):
    if album_id:
        playback.queue_album(album_id)
    elif library.playlists.get(uid_str):
        playback.queue(uid_str)
    else:
        print(f"no data for card {uid_str} — write a Navidrome album ID to the card")
        syslog.syslog(syslog.LOG_WARNING, f"unrecognized tag {uid_str}")

try:
    playback.init()
    monitor = NFCMonitor(
        on_card_detected=handle_new_card,
    ).start()
    VolumeControl().start()
    

    stop_event.wait()
except Exception as e:
    print(f"Error: {e}")
