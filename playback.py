import board
import media
import library
import busio
import syslog
from time import sleep
from digitalio import DigitalInOut, Pull
from traceback import print_exc, format_exc
from watch_reload import start_watch

#PIN_SWITCH_MUTE = board.D5
#PIN_SWITCH_MODE = board.D6
#PIN_ROTARY_FORWARD = board.D16
#PIN_ROTARY_BACKWARD = board.D20
#PIN_ROTARY_CLICK = board.D13

CLK_PIN = 17  # Pin 11 - Clock
DT_PIN  = 27  # Pin 13 - Data
SW_PIN  = 22  # Pin 15 - Switch/Button (to GND, PUD_UP)

def error():
    exc = format_exc()
    print(exc)
    sleep(1)

def outputs_volume(outputs: list[str], volume: int):
    try:
        for item in outputs:
            media.volume(item, volume)
    except:
        error()

def queue(id):
    data: dict[str, str] = library.playlists.get(id)
    if not data:
        print(f"no data for {id}, add new tag to library")
        syslog.syslog(syslog.LOG_WARNING, f"new tag {id}")
        return

    try:
        media.queue(data)
        media.repeat("all")
    except:
        error()
        return

    sleep(1)


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
