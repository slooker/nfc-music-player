# playback.py (top of file)
import os
import board
import media
import library
import busio
import syslog
from time import sleep
from digitalio import DigitalInOut, Pull
from traceback import print_exc, format_exc
from env import load_env
from watch_reload import start_watch
from kv_lookup import RedisClient
from tag_store import get_entry

load_env()  # reads .env into os.environ if present

def _truthy(s: str) -> bool:
    return str(s).lower() in ("1", "true", "yes", "on")

USE_REDIS = _truthy(os.getenv("USE_REDIS", "false"))
REDIS_HOST = os.getenv("REDIS_HOST", "192.168.0.66")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
# prefer .env, then fall back to secrets['redis_password']
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "")

# Redis client (only created if enabled)
_redis = RedisClient(REDIS_HOST, REDIS_PORT, REDIS_PASSWORD) if USE_REDIS else None

def error():
    exc = format_exc()
    print(exc)
    sleep(1)

def _lookup_by_id(tag_id: str) -> dict | None:
    """
    If USE_REDIS: GET <tag_id> from Redis and return {"uris": <value>, "shuffle": "false"}.
    Else/fallback: library.playlists.get(tag_id).
    """
    if _redis:
        try:
            uris = _redis.get(tag_id)
        except Exception:
            uris = None
        if uris:
            return {"uris": uris, "shuffle": "false"}
    return library.playlists.get(tag_id)

def queue(id):
    data = get_entry(id)
    if not data:
        print(f"no data for {id}, add new tag to Redis or library")
        import syslog
        syslog.syslog(syslog.LOG_WARNING, f"new tag {id}")
        return
    try:
        media.queue(data)
        media.repeat("all")
    except Exception:
        from traceback import format_exc
        print(format_exc())
        from time import sleep
        sleep(1)
        return
    from time import sleep
    sleep(1)

def queue(id):
    data = get_entry(id)
    if not data:
        print(f"no data for {id}, add new tag to Redis or library")
        import syslog
        syslog.syslog(syslog.LOG_WARNING, f"new tag {id}")
        return
    try:
        media.queue(data)
        media.repeat("all")
    except Exception:
        from traceback import format_exc
        print(format_exc())
        from time import sleep
        sleep(1)
        return
    from time import sleep
    sleep(1)

def outputs_volume(outputs: list[str], volume: int):
    try:
        for item in outputs:
            media.volume(item, volume)
    except:
        error()

def stop():
    print("stop")
    try:
        media.stop()
    except:
        error()
        return

def pause():
    print("toogle")
    try:
        playing = media.player()["state"] == "play"
    except:
        error()
        return

    if playing:
        print("pause")
        try:
            media.pause()
        except:
            error()
            return
    else:
        print("resume")
        try:
            media.play()
        except:
            error()
            return


def next():
    print("next track")
    try:
        media.next()
    except:
        error()

def change_volume(volume: int):
    print(f"change volume to {volume}")
    try:
        media.volume(volume)
    except:
        error()

def previous():
    print("previous track")
    try:
        media.previous()
    except:
        error()

def init():
    print("waiting for media server")

    while True:
        sleep(0.5)
        try:
            if media.library()["updating"] == False:
                print("library updated")
                break
        except:
            pass

    print("media server ready")
