import hashlib
import json
import random
import secrets
import socket
import subprocess
import time
from requests import get

# https://www.subsonic.org/pages/api.jsp

## Navidrome server URL
NAVIDROME_URL = "https://music.slooker.us"

## Subsonic API credentials — update before deploying
USERNAME = "your-username"
PASSWORD = "your-password"

## Subsonic API client info
CLIENT = "nfc-player"
API_VERSION = "1.16.1"

## mpv IPC socket path
MPV_SOCKET = "/tmp/mpv-socket"

## ALSA softvol control name (from .asoundrc)
ALSA_CONTROL = "Softvol"

## Active mpv subprocess
_mpv_process = None


# ── Internal helpers ──────────────────────────────────────────────────────────

def _auth_params() -> str:
    """Return Subsonic token-auth query string (generates a fresh salt each call)."""
    salt = secrets.token_hex(8)
    token = hashlib.md5((PASSWORD + salt).encode()).hexdigest()
    return f"u={USERNAME}&t={token}&s={salt}&v={API_VERSION}&c={CLIENT}&f=json"


def _subsonic_get(endpoint: str, auth: str = None, **params) -> dict:
    """GET /rest/<endpoint>.view and return the subsonic-response body.

    Pass `auth` explicitly when you need the same token across multiple calls
    (e.g. building a list of stream URLs).
    """
    if auth is None:
        auth = _auth_params()
    url = f"{NAVIDROME_URL}/rest/{endpoint}.view?{auth}"
    if params:
        url += "&" + "&".join(f"{k}={v}" for k, v in params.items())
    response = get(url)
    response.raise_for_status()
    body = response.json()["subsonic-response"]
    if body["status"] != "ok":
        msg = body.get("error", {}).get("message", "unknown error")
        raise Exception(f"Subsonic API error: {msg}")
    return body


def _mpv_cmd(cmd: dict) -> dict:
    """Send a JSON IPC command to the running mpv process and return the response."""
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.connect(MPV_SOCKET)
        s.sendall(json.dumps(cmd).encode() + b"\n")
        return json.loads(s.recv(4096))


def _start_mpv(urls: list[str]):
    """Kill any running mpv instance, then start a new one with the given URL playlist."""
    global _mpv_process
    stop()
    args = [
        "mpv",
        "--no-video",
        f"--input-ipc-server={MPV_SOCKET}",
    ] + urls
    _mpv_process = subprocess.Popen(args)
    time.sleep(0.5)  # give mpv time to create the IPC socket


# ── Public API (same signatures as the original OwnTone-based media.py) ───────

def library() -> dict:
    """Check whether the Navidrome server is reachable and ready.

    Returns {"updating": False} on success (compatible with playback.init()).
    """
    try:
        _subsonic_get("ping")
        return {"updating": False}
    except Exception:
        return {"updating": True}


def player() -> dict:
    """Return current player state as {"state": "play"|"pause"|"stop"}."""
    global _mpv_process
    if _mpv_process is None or _mpv_process.poll() is not None:
        return {"state": "stop"}
    try:
        result = _mpv_cmd({"command": ["get_property", "pause"]})
        paused = result.get("data", True)
        return {"state": "pause" if paused else "play"}
    except Exception:
        return {"state": "stop"}


def volume(vol: int):
    """Set ALSA softvol to the given level (0–100)."""
    vol = max(0, min(100, int(vol)))
    subprocess.run(
        ["amixer", "sset", ALSA_CONTROL, f"{vol}%"],
        capture_output=True,
    )


def queue(args: dict):
    """Fetch album songs from Navidrome and start mpv playback.

    args keys:
        id      — Navidrome album ID (required)
        shuffle — "true" or "false" (default "false")
    """
    album_id = args["id"]
    shuffle = args.get("shuffle", "false") == "true"

    # Generate auth once so all stream URLs share the same token/salt
    auth = _auth_params()
    data = _subsonic_get("getAlbum", auth=auth, id=album_id)
    songs = data["album"]["song"]

    if shuffle:
        random.shuffle(songs)

    urls = [
        f"{NAVIDROME_URL}/rest/stream.view?id={s['id']}&{auth}"
        for s in songs
    ]
    _start_mpv(urls)


def repeat(state: str):
    """Set repeat mode: "all", "single", or "off"."""
    if state == "all":
        _mpv_cmd({"command": ["set_property", "loop-playlist", "inf"]})
    elif state == "single":
        _mpv_cmd({"command": ["set_property", "loop-file", "inf"]})
    else:
        _mpv_cmd({"command": ["set_property", "loop-playlist", "no"]})
        _mpv_cmd({"command": ["set_property", "loop-file", "no"]})


def pause():
    _mpv_cmd({"command": ["set_property", "pause", True]})


def play():
    _mpv_cmd({"command": ["set_property", "pause", False]})


def stop():
    global _mpv_process
    if _mpv_process and _mpv_process.poll() is None:
        _mpv_process.terminate()
        try:
            _mpv_process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            _mpv_process.kill()
    _mpv_process = None


def next():
    _mpv_cmd({"command": ["playlist-next"]})


def previous():
    _mpv_cmd({"command": ["playlist-prev"]})


if __name__ == "__main__":
    pass
