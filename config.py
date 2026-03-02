# config.py
import os

# Toggle Redis lookups
USE_REDIS = os.getenv("USE_REDIS", "false").lower() in ("1", "true", "yes")

# Redis connection
REDIS_HOST = os.getenv("REDIS_HOST", "192.168.0.66")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

# Password: prefer secrets.py['redis_password'] but allow env var fallback
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD")
try:
    from secrets import secrets  # optional file you already use
    REDIS_PASSWORD = secrets.get("redis_password", REDIS_PASSWORD)
except Exception:
    pass