# tag_store.py — single source of truth for NFC→URI lookups (ENV-only)

import os
from env import load_env
from kv_lookup import RedisClient
import library

load_env()  # pulls in .env if present

def _truthy(s: str) -> bool:
    return str(s).lower() in ("1", "true", "yes", "on")

USE_REDIS = _truthy(os.getenv("USE_REDIS", "false"))
REDIS_HOST = os.getenv("REDIS_HOST", "192.168.0.66")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_USER = os.getenv("REDIS_USER") or "default"
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD") or None

_client = RedisClient(
    host=REDIS_HOST,
    port=REDIS_PORT,
    username=REDIS_USER,
    password=REDIS_PASSWORD,
)

def get_entry(tag_id: str) -> dict | None:
    """
    Returns {"uris": "...", "shuffle": "false"} or None.
    Order:
      1) Redis GET <tag_id>  (if enabled)
      2) library.playlists.get(tag_id)
    """
    if _client:
        try:
            uris = _client.get(tag_id)
        except Exception:
            uris = None
        if uris:
            return {"uris": uris, "shuffle": "false"}
    return library.playlists.get(tag_id)

def known(tag_id: str) -> bool:
    return get_entry(tag_id) is not None
