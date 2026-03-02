# env.py - minimal .env loader (no deps)
import os

def load_env(path: str = ".env") -> None:
    try:
        with open(path, "r") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                # don't overwrite existing env (e.g., systemd Environment=...)
                os.environ.setdefault(k, v)
    except FileNotFoundError:
        pass
