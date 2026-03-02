# kv_lookup.py
import socket

class RedisAuthError(Exception):
    pass

class RedisClient:
    def __init__(self, host="127.0.0.1", port=6379, password=None, username=None, timeout=3.0):
        self.host = host
        self.port = port
        self.password = password
        self.username = username
        self.timeout = timeout

    def _array(self, items):
        out = b"*%d\r\n" % len(items)
        for it in items:
            if isinstance(it, str):
                it = it.encode("utf-8")
            out += b"$%d\r\n%s\r\n" % (len(it), it)
        return out

    def _open(self):
        s = socket.socket()
        s.settimeout(self.timeout)
        s.connect((self.host, self.port))
        return s

    def _auth_legacy(self):
        """AUTH <password> on a fresh socket."""
        s = self._open()
        try:
            s.sendall(self._array([b"AUTH", self.password]))
            resp = s.recv(4096)
            return s, resp
        except Exception:
            s.close()
            raise

    def _auth_userpass(self):
        """AUTH <username> <password> on a fresh socket."""
        s = self._open()
        try:
            user = (self.username or "default")
            s.sendall(self._array([b"AUTH", user, self.password]))
            resp = s.recv(4096)
            return s, resp
        except Exception:
            s.close()
            raise

    def _authed_socket(self):
        """Return an authenticated socket or raise RedisAuthError."""
        # No auth needed
        if not self.password:
            return self._open()

        # First: mimic redis-cli -a (one-arg AUTH)
        s, resp = self._auth_legacy()
        if resp.startswith(b"+OK"):
            return s

        # If server complains about args, try two-arg AUTH on a new socket
        s.close()
        s2, resp2 = self._auth_userpass()
        if resp2.startswith(b"+OK"):
            return s2

        # Neither form worked
        msg1 = resp.decode("utf-8", "ignore").strip()
        msg2 = resp2.decode("utf-8", "ignore").strip()
        s2.close()
        raise RedisAuthError(f"AUTH failed. legacy='{msg1}' userpass='{msg2}'")

    def get(self, key):
        # Open and authenticate
        s = self._authed_socket()
        try:
            s.sendall(self._array([b"GET", key]))
            resp = s.recv(4096)
        finally:
            s.close()

        # Parse bulk string replies
        if not resp or resp.startswith(b"$-1"):
            return None
        if resp.startswith(b"$"):
            nl = resp.find(b"\r\n")
            if nl == -1:
                return None
            try:
                n = int(resp[1:nl])
            except ValueError:
                return None
            start = nl + 2
            return resp[start:start+n].decode("utf-8", "ignore")
        if resp.startswith(b"-"):
            # e.g., -NOAUTH, -WRONGPASS
            raise RedisAuthError(resp.decode("utf-8", "ignore").strip())
        return None
