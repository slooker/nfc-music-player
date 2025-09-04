# code.py — Pico W (CircuitPython) web UI + PN532 + Redis + search proxy

import time
import wifi
import socketpool
import ipaddress
import json
from secrets import secrets  # {"ssid":"...", "password":"...", "redis_password":"..."}

# ---- Configuration ----
WIFI_SSID = secrets["ssid"]
WIFI_PASS = secrets["password"]

REDIS_HOST = "192.168.0.66"
REDIS_PORT = 6379
REDIS_PASSWORD = secrets.get("redis_password")

# Proxy target for /search. If your API is NOT on the Pico, set MUSIC_HOST to that machine's IP!
MUSIC_HOST = "192.168.0.142"   # <-- change to "192.168.0.xx" if needed
MUSIC_PORT = 3689

# PN532 wiring (SPI1 on Pico W): SCK=GP10(14), MOSI=GP11(15), MISO=GP12(16), CS=GP8(11)
USE_PN532 = True  # set False if you want to run without the PN532 connected

# ---- PN532 (SPI1) ----
last_uid = ""  # updated as we read cards

if USE_PN532:
    import board, busio
    from digitalio import DigitalInOut
    from adafruit_pn532.spi import PN532_SPI

    spi = busio.SPI(clock=board.GP10, MOSI=board.GP11, MISO=board.GP12)
    while not spi.try_lock():
        pass
    try:
        spi.configure(baudrate=400_000, polarity=0, phase=0, bits=8)
    finally:
        spi.unlock()

    cs = DigitalInOut(board.GP8)
    pn = PN532_SPI(spi, cs, debug=False)
    time.sleep(0.4)
    try:
        ic, ver, rev, support = pn.firmware_version
        print("PN532:", ver, rev)
        pn.SAM_configuration()
    except Exception as e:
        print("PN532 init failed:", repr(e))
        USE_PN532 = False

def poll_nfc_once():
    global last_uid
    if not USE_PN532:
        return
    try:
        uid = pn.read_passive_target(timeout=0.2)  # was 0.01
        if uid:
            last_uid = "".join(["%02X" % b for b in uid])
    except Exception:
        pass


# ---- Redis minimal client (RESP2) ----
def _resp_bulk(b):
    if isinstance(b, str):
        b = b.encode("utf-8")
    return b"$%d\r\n%s\r\n" % (len(b), b)

def _resp_array(items):
    out = b"*%d\r\n" % len(items)
    for it in items:
        out += _resp_bulk(it)
    return out

# ---- Tiny HTTP helpers ----
def redis_get_str(key):
    """GET key -> str or None."""
    raw = redis_cmd(pool, b"GET", key)
    val = parse_redis_simple(raw)
    return val if isinstance(val, str) else None

def fetch_album(pool_obj, album_id):
    """
    Fetch album metadata from the music server.
    Returns a dict (parsed JSON) on success, or None on failure.
    """
    try:
        status, body = http_get_json_via_proxy(pool_obj, MUSIC_HOST, MUSIC_PORT, "/api/library/albums/" + album_id)
        if status == 200 and body:
            try:
                return json.loads(body.decode("utf-8"))
            except Exception:
                return None
        return None
    except Exception:
        return None
    
def _send_all(conn, data, chunk=1024):
    """Send all bytes in small chunks to avoid resets."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    mv = memoryview(data)
    total = 0
    L = len(mv)
    while total < L:
        sent = conn.send(mv[total: total + chunk])
        if not sent:
            break
        total += sent

def http_send(conn, status="200 OK", body=b"OK", ctype="text/plain"):
    if isinstance(body, str):
        body = body.encode("utf-8")
    headers = (
        "HTTP/1.1 " + status + "\r\n"
        "Content-Type: " + ctype + "\r\n"
        "Content-Length: " + str(len(body)) + "\r\n"
        "Connection: close\r\n"
        "\r\n"
    )
    _send_all(conn, headers)
    _send_all(conn, body)

def read_http_request(conn, buf, timeout_s=3.0):
    """
    Read until end-of-headers or buffer fills. Returns a decoded request string
    or '' on timeout/empty.
    """
    conn.settimeout(timeout_s)
    total = 0
    while True:
        try:
            n = conn.recv_into(memoryview(buf)[total:])
        except Exception:
            # timeout or recv error
            break
        if not n:
            break
        total += n
        if total >= 4 and buf[0:total].find(b"\r\n\r\n") != -1:
            break
        if total >= len(buf):
            break
    if total <= 0:
        return ""
    return bytes(memoryview(buf)[:total]).decode("utf-8", "ignore")

def _recv_once(sock, maxlen=4096, timeout=2.0):
    buf = bytearray(maxlen)
    try:
        sock.settimeout(timeout)
        n = sock.recv_into(buf)
        if not n:
            return b""
        return bytes(memoryview(buf)[:n])
    except Exception:
        return b""

def redis_cmd(pool, cmd: bytes, *args: str) -> bytes:
    s = pool.socket(pool.AF_INET, pool.SOCK_STREAM)
    try:
        s.settimeout(3)
        s.connect((REDIS_HOST, REDIS_PORT))
        if REDIS_PASSWORD:
            s.send(_resp_array([b"AUTH", REDIS_PASSWORD]))
            _ = _recv_once(s, 256, 2.0)  # +OK or -ERR
        s.send(_resp_array([cmd] + list(args)))
        return _recv_once(s, 4096, 2.0)
    finally:
        s.close()

def parse_redis_simple(resp):
    if not resp:
        return None
    if resp.startswith(b"+"):          # +OK
        return resp[1:].split(b"\r\n",1)[0].decode("utf-8","ignore")
    if resp.startswith(b"$-1"):        # nil
        return None
    if resp.startswith(b"$"):          # $<len>\r\n<data>\r\n
        nl = resp.find(b"\r\n")
        if nl == -1: return None
        try:
            ln = int(resp[1:nl])
        except Exception:
            return None
        start = nl + 2
        return resp[start:start+ln].decode("utf-8","ignore")
    if resp.startswith(b"-"):          # -ERR ...
        return resp.decode("utf-8","ignore")
    if resp.startswith(b":"):          # :<int>
        try: return int(resp[1:].split(b"\r\n",1)[0])
        except Exception: return None
    return resp.decode("utf-8","ignore")

def url_decode(s):
    out, i = [], 0
    while i < len(s):
        ch = s[i]
        if ch == "+":
            out.append(" "); i += 1
        elif ch == "%" and i + 2 < len(s):
            try:
                out.append(chr(int(s[i+1:i+3], 16))); i += 3
            except ValueError:
                out.append(ch); i += 1
        else:
            out.append(ch); i += 1
    return "".join(out)

def parse_query(qs: str) -> dict:
    params = {}
    if not qs: return params
    for part in qs.split("&"):
        if "=" in part:
            k, v = part.split("=", 1)
            params[url_decode(k)] = url_decode(v)
    return params

# ---- Proxy HTTP GET (handles chunked) ----
def http_get_json_via_proxy(pool, host, port, path):
    s = pool.socket(pool.AF_INET, pool.SOCK_STREAM)
    try:
        s.settimeout(5)
        s.connect((host, port))
        # Build the HTTP request without f-strings
        req = (
            "GET " + path + " HTTP/1.1\r\n"
            "Host: " + host + "\r\n"
            "User-Agent: PicoW/1.0\r\n"
            "Accept: application/json\r\n"
            "Connection: close\r\n"
            "\r\n"
        ).encode("utf-8")
        s.send(req)

        # Read entire response
        chunks = bytearray()
        buf = bytearray(2048)
        while True:
            n = s.recv_into(buf)
            if n <= 0:
                break
            chunks += buf[:n]

        # Split headers/body
        sep = chunks.find(b"\r\n\r\n")
        if sep == -1:
            return 502, b'{"error":"bad upstream response"}'
        header_bytes = bytes(chunks[:sep])
        body = bytes(chunks[sep+4:])

        # Parse status
        first_line_end = header_bytes.find(b"\r\n")
        status_line = header_bytes[:first_line_end].decode("utf-8", "ignore")
        try:
            status_code = int(status_line.split(" ")[1])
        except Exception:
            status_code = 502

        headers_text = header_bytes.decode("utf-8", "ignore").lower()
        if "transfer-encoding: chunked" in headers_text:
            body = dechunk(body)

        return status_code, body
    finally:
        s.close()

def dechunk(data: bytes) -> bytes:
    """Dechunk HTTP/1.1 chunked body -> raw bytes."""
    out = bytearray()
    i = 0
    L = len(data)
    while True:
        j = data.find(b"\r\n", i)
        if j == -1: break
        size_hex = data[i:j].split(b";", 1)[0]
        try:
            size = int(size_hex, 16)
        except ValueError:
            break
        i = j + 2
        if size == 0:
            # Optional trailer, consume till final CRLF if present
            k = data.find(b"\r\n\r\n", i)
            return bytes(out)
        if i + size > L:  # incomplete (shouldn't happen since we read till close)
            out += data[i:]
            return bytes(out)
        out += data[i:i+size]
        i += size + 2  # skip chunk + CRLF
    return bytes(out)

# ---- Serve HTML UI ----
INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Pico W – NFC → Redis Mapper</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
:root { font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; }
body { margin:0; padding:1rem; background:#0b1220; color:#e6e9ef; }
h1 { margin:0 0 1rem; font-size:1.25rem; }
.card { background:#131a2a; border:1px solid #263149; border-radius:12px; padding:1rem; }
.grid { display:grid; gap:.75rem; }
.row { display:grid; grid-template-columns:140px 1fr; align-items:center; gap:.5rem; }
input[type="text"]{ width:100%; padding:.6rem .7rem; background:#0f1524; color:#e6e9ef; border:1px solid #2a3550; border-radius:10px; }
input[readonly]{ opacity:.9; }
button{ padding:.6rem .9rem; border:1px solid #3a4c78; background:#1a2440; color:#e6e9ef; border-radius:10px; cursor:pointer; }
button:hover{ background:#223057; }
.actions{ display:flex; gap:.5rem; flex-wrap:wrap; }
.results{ display:grid; grid-template-columns:repeat(auto-fill,minmax(220px,1fr)); gap:.75rem; }
.item{ display:grid; grid-template-columns:64px 1fr; gap:.6rem; padding:.6rem; border:1px solid #263149; border-radius:10px; background:#0f1524; cursor:pointer; }
.item:hover{ border-color:#3a4c78; background:#142045; }
.item.selected{ outline:2px solid #5aa0ff; }
.cover{ width:64px; height:64px; background:#1b2134; border-radius:8px; object-fit:cover; }
.meta{ display:grid; gap:.2rem; }
.title{ font-weight:600; }
.artist,.subtle{ color:#a9b3c9; font-size:.9rem; }
.status{ min-height:1.2rem; color:#9fd68f; }
.error{ color:#ff9797; }
.muted{ color:#a9b3c9; font-size:.9rem; }
.footer{ margin-top:1rem; color:#93a1ba; font-size:.85rem; }
.two-col{ display:grid; grid-template-columns:1fr 1fr; gap:.75rem; }
@media (max-width:720px){ .row{ grid-template-columns:1fr; } .two-col{ grid-template-columns:1fr; } }
</style>
</head>
<body>
<h1>Pico W – Map NFC Card → Album URI</h1>

<div class="grid">
  <div class="card grid">
    <div class="row">
      <label for="searchInput">Search</label>
      <div class="actions">
        <input id="searchInput" type="text" placeholder="e.g., Black Holes and Revelations" />
        <button id="searchBtn">Search</button>
      </div>
    </div>

    <div class="muted">Results (albums)</div>
    <div id="results" class="results"></div>
    <div id="searchStatus" class="status"></div>
  </div>

  <div class="two-col">
    <div class="card grid">
      <div class="row">
        <label for="nfcField">NFC Card</label>
        <div class="actions">
            <input id="nfcField" type="text" readonly placeholder="Waiting for card…" />
            <button id="refreshNfcBtn" title="Poll /nfc">Refresh NFC</button>
            <button id="checkBtn" title="Lookup current mapping">Check</button>
            <label style="display:inline-flex;align-items:center;gap:.35rem;margin-left:.5rem;">
              <input id="liveNfcChk" type="checkbox"> Live NFC
            </label>
        </div>
      </div>
      <div class="muted">Pico exposes <code>/nfc</code> returning <code>{"uid":"43A2EB33"}</code>.</div>
    </div>

    <div class="card grid">
      <div class="row">
        <label for="uriField">Selected URI</label>
        <input id="uriField" type="text" readonly placeholder="Click a result to fill this" />
      </div>
      <div class="actions">
        <button id="saveBtn">Save to Redis</button>
        <div id="saveStatus" class="status"></div>
      </div>
      <div class="muted">Saves as <code>&lt;NFC UID&gt; : &lt;URI&gt;</code> via <code>/set?key=&amp;value=</code>.</div>
    </div>
  </div>

  <div class="card footer">
    <div><b>Note</b>: This page calls <code>/search</code> on the Pico, which proxies to <code>http://music.local/api/search</code>.</div>
  </div>
</div>

<script>
const PICO_BASE = '';
const searchInput   = document.getElementById('searchInput');
const searchBtn     = document.getElementById('searchBtn');
const resultsEl     = document.getElementById('results');
const searchStatus  = document.getElementById('searchStatus');
const nfcField      = document.getElementById('nfcField');
const refreshNfcBtn = document.getElementById('refreshNfcBtn');
const uriField      = document.getElementById('uriField');
const saveBtn       = document.getElementById('saveBtn');
const saveStatus    = document.getElementById('saveStatus');
const checkBtn = document.getElementById('checkBtn');

let selectedItemEl = null;

function escapeHtml(s){ return s.replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }
function toAlbumURI(item){ return (item.uri && item.uri.startsWith('library:')) ? item.uri : ('library:album:' + item.id); }
function albumArtworkUrl(item){ try { return new URL(item.artwork_url, 'http://localhost').toString(); } catch { return ''; } }

function clearResults(){
  resultsEl.innerHTML = '';
  uriField.value = '';
  if (selectedItemEl) selectedItemEl.classList.remove('selected');
  selectedItemEl = null;
}

async function doSearch(){
  clearResults();
  const q = (searchInput.value || '').trim();
  if (!q){ searchStatus.textContent = 'Enter something to search.'; return; }
  searchStatus.textContent = 'Searching…';
  try{
    const url = `${PICO_BASE}/api/search?type=${encodeURIComponent('tracks,artists,albums,playlists')}&query=${encodeURIComponent(q)}`;
    const resp = await fetch(url, {method:'GET'});
    if (!resp.ok) throw new Error('HTTP ' + resp.status);
    const data = await resp.json();
    const albums = (data && data.albums && Array.isArray(data.albums.items)) ? data.albums.items : [];
    if (!albums.length){ searchStatus.textContent = 'No albums found.'; return; }
    for (const item of albums){
      const el = document.createElement('div');
      el.className = 'item';
      el.innerHTML = `
        <img class="cover" src="${escapeHtml(albumArtworkUrl(item))}" onerror="this.style.visibility='hidden'">
        <div class="meta">
          <div class="title">${escapeHtml(item.name || '(unknown)')}</div>
          <div class="artist">${escapeHtml(item.artist || '')}</div>
          <div class="subtle">${item.year ? escapeHtml(String(item.year)) : ''}</div>
        </div>`;
      el.addEventListener('click', () => {
        if (selectedItemEl) selectedItemEl.classList.remove('selected');
        el.classList.add('selected'); selectedItemEl = el;
        uriField.value = toAlbumURI(item);
      });
      resultsEl.appendChild(el);
    }
    searchStatus.textContent = `Found ${albums.length} album${albums.length>1?'s':''}.`;
  }catch(err){
    searchStatus.innerHTML = `<span class="error">Search failed: ${escapeHtml(err.message)}</span>`;
  }
}

async function checkCard(){
  const uid = (nfcField.value || '').trim();
  if (!uid){ saveStatus.innerHTML = '<span class="error">No NFC UID.</span>'; return; }
  try{
    const r = await fetch(`${PICO_BASE}/lookup?key=${encodeURIComponent(uid)}`);
    if (!r.ok){ throw new Error('HTTP ' + r.status); }
    const j = await r.json();
    if (j.found){
      const human = j.title || j.value || '(unknown)';
      saveStatus.textContent = `Card ${uid} is assigned to: ${human}`;
    } else {
      saveStatus.textContent = `Card ${uid} is not assigned yet.`;
    }
  }catch(err){
    saveStatus.innerHTML = `<span class="error">Lookup failed: ${String(err.message || err)}</span>`;
  }
}

async function pollNfcOnce(){
  try{ const r = await fetch(`${PICO_BASE}/nfc`, {cache:'no-store'});
       if (!r.ok) return;
       const j = await r.json();
       if (j && j.uid) nfcField.value = j.uid; }catch{}
}

checkBtn.addEventListener('click', checkCard);
searchBtn.addEventListener('click', doSearch);
searchInput.addEventListener('keydown', e => { if (e.key === 'Enter') doSearch(); });
refreshNfcBtn.addEventListener('click', pollNfcOnce);

async function saveMapping(){
  saveStatus.textContent = '';
  const uid = (nfcField.value || '').trim();
  const uri = (uriField.value || '').trim();
  if (!uid){ saveStatus.innerHTML = '<span class="error">No NFC UID.</span>'; return; }
  if (!uri){ saveStatus.innerHTML = '<span class="error">No URI selected.</span>'; return; }

  // Preflight: if this card already has EXACTLY this URI, skip saving
  try {
    const check = await fetch(`${PICO_BASE}/lookup?key=${encodeURIComponent(uid)}`);
    if (check.ok) {
      const j = await check.json();
      if (j && j.found && j.value === uri) {
        const shown = j.title || j.value || '(current)';
        saveStatus.textContent = `No change — card ${uid} already mapped to: ${shown}`;
        return;
      }
    }
  } catch(_) { /* ignore and fall through */ }

  async function doSet(force){
    const url = `${PICO_BASE}/set?key=${encodeURIComponent(uid)}&value=${encodeURIComponent(uri)}${force?'&force=1':''}`;
    const r = await fetch(url, { method: 'GET' });
    const text = await r.text();
    let j = null; try { j = JSON.parse(text); } catch {}
    return { r, ok: r.ok, status: r.status, text, j };
  }

  try {
    let { r, ok, status, text, j } = await doSet(false);
    if (ok){
      if (j && j.unchanged) {
        // Server confirmed idempotent save
        const shown = uri; // optional: keep simple; you could reuse the preflight title
        saveStatus.textContent = `No change — card ${uid} already mapped to: ${shown}`;
      } else {
        saveStatus.textContent = `Saved: ${uid} → ${uri}`;
      }
      return;
    }

    // ---- 409 handling (unchanged from your last version) ----
    if (status === 409) {
      let info = null;
      try { info = JSON.parse(text); } catch {}

      if (info && info.error === 'uri_in_use') {
        const who = info.by || '(another card)';
        const title = info.by_title ? ` (${info.by_title})` : '';
        saveStatus.innerHTML = `<span class="error">That album is already assigned to card ${who}${title}. Choose a different album.</span>`;
        return;
      }

      const human = info && (info.current_title ||
                    ((info.current_artist && info.current_name)
                       ? (info.current_artist + ' - ' + info.current_name)
                       : ''));
      const fallback = info && info.current ? info.current : '(unknown)';
      const shown = human || fallback;

      const msg = `This card is already assigned to:\n${shown}\n\nOverwrite with:\n${uri}?`;
      if (confirm(msg)) {
        ({ r, ok, status, text, j } = await doSet(true));
        if (ok){ saveStatus.textContent = `Overwritten: ${uid} → ${uri}`; return; }
        throw new Error(text || ('HTTP ' + status));
      } else {
        saveStatus.innerHTML = `<span class="error">Not saved — card already assigned to ${shown}.</span>`;
        return;
      }
    }
    // ---------------------------------------------------------

    // Any other non-OK
    throw new Error(text || ('HTTP ' + status));
  } catch (err) {
    saveStatus.innerHTML = `<span class="error">Save failed: ${String(err.message || err)}</span>`;
  }
}

const liveNfcChk = document.getElementById('liveNfcChk');
let nfcTimer = null;

function setLiveNfc(on) {
  if (on && !document.hidden) {
    if (!nfcTimer) nfcTimer = setInterval(pollNfcOnce, 1500); // gentle 1.5s polling
  } else {
    if (nfcTimer) { clearInterval(nfcTimer); nfcTimer = null; }
  }
}
liveNfcChk.addEventListener('change', () => setLiveNfc(liveNfcChk.checked));

// Pause polling when the tab isn’t visible
document.addEventListener('visibilitychange', () => {
  setLiveNfc(liveNfcChk.checked && !document.hidden);
});

saveBtn.addEventListener('click', saveMapping);

// initial NFC fetch
pollNfcOnce();
</script>
</body></html>
"""

def open_server(cur_pool, port=80, attempts=18, delay=0.5):
    """
    Try to bind a server socket. If the port is 'busy', retry a bunch of times.
    After several failures, briefly reset Wi-Fi, reconnect, and rebuild the socket pool.
    Returns: (srv_socket, socket_pool)
    """
    last_err = None
    backoff = delay
    pool_ref = cur_pool  # local working copy; may be rebuilt after radio reset

    for i in range(attempts):
        s = None
        try:
            s = pool_ref.socket(pool_ref.AF_INET, pool_ref.SOCK_STREAM)
            s.settimeout(0.1)  # short accept timeout so main loop can do other work
            s.bind(("0.0.0.0", port))
            s.listen(2)
            return s, pool_ref
        except OSError as e:
            last_err = e
            busy = getattr(e, "errno", None) in (112, 98)  # EADDRINUSE variants
            try:
                if s:
                    s.close()
            except Exception:
                pass

            # After a few attempts, reset Wi-Fi and rebuild the pool
            if busy and (i in (4, 9, 14)):
                try:
                    print("Port busy; resetting Wi-Fi…")
                    wifi.radio.enabled = False
                    time.sleep(0.8)
                    wifi.radio.enabled = True
                    time.sleep(0.8)
                except Exception:
                    time.sleep(0.5)

                # Reconnect and rebuild pool
                try:
                    ensure_wifi()
                except Exception as _e:
                    print("Reconnect failed:", repr(_e))
                    time.sleep(1.0)
                try:
                    pool_ref = socketpool.SocketPool(wifi.radio)
                except Exception:
                    pass

            # Backoff before next try
            time.sleep(backoff)
            backoff = backoff + 0.25
            continue
        except Exception as e:
            last_err = e
            break

    # All attempts failed
    raise last_err

# ---- Wi-Fi bring-up (idempotent) ----
def ensure_wifi():
    try:
        if wifi.radio.ipv4_address:
            print("Already connected:", wifi.radio.ipv4_address); return
    except Exception:
        pass
    print("Connecting to Wi-Fi…")
    wifi.radio.connect(WIFI_SSID, WIFI_PASS)
    print("Connected:", wifi.radio.ipv4_address)

def _port80_busy(pool):
    try:
        s = pool.socket(pool.AF_INET, pool.SOCK_STREAM)
        s.settimeout(0.5)
        s.connect((str(wifi.radio.ipv4_address), 80))
        s.close()
        return True  # connect worked -> somebody is already listening
    except Exception:
        return False

ensure_wifi()
pool = socketpool.SocketPool(wifi.radio)

print("Pre-check: port 80 busy?", _port80_busy(pool))

# ---- HTTP server ----
PORT = 80  # keep using 80
time.sleep(0.25)
srv, pool = open_server(pool, port=PORT)  # <-- unpack tuple
print("HTTP server: http://%s%s" % (wifi.radio.ipv4_address, "" if PORT == 80 else (":" + str(PORT))))
buf = bytearray(4096)

def handle_request(conn, req_text):
    # Parse first line
    line = req_text.split("\r\n", 1)[0]
    parts = line.split(" ")
    if len(parts) < 2:
        http_send(conn, "400 Bad Request", "Bad request"); return
    method, path = parts[0], parts[1]
    if method != "GET":
        http_send(conn, "405 Method Not Allowed", "Use GET"); return

    # route + params
    if "?" in path:
        route, qs = path.split("?", 1)
        params = parse_query(qs)
    else:
        route, params = path, {}

    if route == "/":
        http_send(conn, "200 OK", INDEX_HTML, "text/html")
    elif route == "/nfc":
        # Try a fresh read right now
        poll_nfc_once()
        body = json.dumps({"uid": last_uid or ""})
        http_send(conn, "200 OK", body, "application/json")
    elif route == "/set":
        key = params.get("key"); val = params.get("value")
        force = params.get("force", "")
        if not key or val is None:
            http_send(conn, "400 Bad Request", "Provide key and value"); return
        try:
            # Reverse-lookup protection: prevent the same album URI being assigned to another UID
            idx_owner = redis_get_str("uri:" + val)
            if idx_owner and idx_owner != key:
                # Enrich with album title from the *target* URI if possible
                by_title = ""
                if val.startswith("library:album:"):
                    album_id2 = val.split(":")[-1]
                    meta2 = fetch_album(pool, album_id2)
                    if meta2:
                        a2 = meta2.get("artist", "")
                        n2 = meta2.get("name", "")
                        if a2 or n2:
                            by_title = (a2 + " - " + n2).strip(" -")
                body = {"error":"uri_in_use", "uri": val, "by": idx_owner}
                if by_title:
                    body["by_title"] = by_title
                http_send(conn, "409 Conflict", json.dumps(body), "application/json")
                return

            if force in ("1","true","yes","True"):
                # Allow overwriting this UID's own value, while keeping URI uniqueness.
                old_val = redis_get_str(key)
                # (Index uniqueness already checked above)
                _ = redis_cmd(pool, b"SET", key, val)  # overwrite
                _ = redis_cmd(pool, b"SET", "uri:" + val, key)  # ensure index points to this UID
                if old_val and old_val != val:
                    _ = redis_cmd(pool, b"DEL", "uri:" + old_val)  # clean old index
                http_send(conn, "200 OK", "OK", "text/plain")
            else:
                # Only set if this card UID doesn't already have a value
                raw = redis_cmd(pool, b"SET", key, val, "NX")
                msg = parse_redis_simple(raw)
                if msg is None:
                    # Key already exists → get current and handle idempotency
                    cur_val = redis_get_str(key)
                    if cur_val == val:
                        # Idempotent save: same value already set for this UID
                        http_send(conn, "200 OK", json.dumps({"ok": True, "unchanged": True}), "application/json")
                        return


                    # Enrich with album title for the *current* mapping if possible
                    display = None
                    artist = None
                    name = None
                    album_id = None
                    if cur_val and cur_val.startswith("library:album:"):
                        album_id = cur_val.split(":")[-1]
                        meta = fetch_album(pool, album_id)
                        if meta:
                            artist = meta.get("artist", "")
                            name = meta.get("name", "")
                            if artist or name:
                                display = (artist + " - " + name).strip(" -")

                    resp_obj = {"error": "exists", "key": key, "current": cur_val}
                    if display:
                        resp_obj["current_title"] = display
                        resp_obj["current_artist"] = artist or ""
                        resp_obj["current_name"] = name or ""
                        resp_obj["album_id"] = album_id or ""
                    http_send(conn, "409 Conflict", json.dumps(resp_obj), "application/json")
                else:
                    # New assignment → write reverse index now
                    _ = redis_cmd(pool, b"SET", "uri:" + val, key)
                    http_send(conn, "200 OK", msg, "text/plain")
        except Exception as e:
            http_send(conn, "502 Bad Gateway", "Redis error: " + repr(e))
    elif route == "/get":
        key = params.get("key")
        if not key:
            http_send(conn, "400 Bad Request", "Provide key"); return
        try:
            raw = redis_cmd(pool, b"GET", key)
            http_send(conn, "200 OK", raw.decode("utf-8","ignore"))
        except Exception as e:
            http_send(conn, "502 Bad Gateway", "Redis error: " + repr(e))
    elif route == "/lookup":
        lookup_key = params.get("key", "")
        if not lookup_key:
            http_send(conn, "400 Bad Request", json.dumps({"error":"missing key"}), "application/json"); return
        try:
            cur_val = redis_get_str(lookup_key)
            resp = {"key": lookup_key, "found": bool(cur_val), "value": cur_val or ""}
            if cur_val and cur_val.startswith("library:album:"):
                album_id = cur_val.split(":")[-1]
                meta = fetch_album(pool, album_id)
                if meta:
                    artist = meta.get("artist", "")
                    name = meta.get("name", "")
                    title = (artist + " - " + name).strip(" -")
                    resp["album_id"] = album_id
                    resp["artist"] = artist
                    resp["name"] = name
                    resp["title"] = title
                    if "artwork_url" in meta:
                        resp["artwork_url"] = meta.get("artwork_url")
            http_send(conn, "200 OK", json.dumps(resp), "application/json")
        except Exception as e:
            http_send(conn, "502 Bad Gateway", json.dumps({"error": "lookup_failed", "detail": repr(e)}), "application/json")
    elif route == "/search" or route == "/api/search":
        q = params.get("query", "")
        t = params.get("type", "tracks,artists,albums,playlists")
        upstream_path = "/api/search?type=" + t + "&query=" + q
        try:
            status, body = http_get_json_via_proxy(pool, MUSIC_HOST, MUSIC_PORT, upstream_path)
            ctype = "application/json"
            if status == 200:
                http_send(conn, "200 OK", body, ctype)
            else:
                http_send(conn, str(status) + " Upstream Error", body, ctype)
        except Exception as e:
            http_send(conn, "502 Bad Gateway", json.dumps({"error": repr(e)}), "application/json")
    elif route == "/health":
        http_send(conn, "200 OK", "OK", "text/plain")
    elif route == "/favicon.ico":
        http_send(conn, "204 No Content", b"", "image/x-icon")
    else:
        http_send(conn, "404 Not Found", "Not found")

# ---- Main loop ----
try:
    while True:
        # Background task: poll NFC even when idle
        poll_nfc_once()

        # Non-blocking-ish accept (srv has a short timeout)
        try:
            client, addr = srv.accept()
        except Exception:
            continue

        try:
            # Read request safely (don’t hang forever)
            req_text = read_http_request(client, buf, timeout_s=3.0)
            if not req_text:
                # Nothing useful; close and continue
                try:
                    client.close()
                except Exception:
                    pass
                continue

            # Handle one request
            handle_request(client, req_text)

        except Exception as e:
            # Best-effort error back to client
            try:
                http_send(client, "500 Internal Server Error", "Error: " + repr(e), "text/plain")
            except Exception:
                pass
        finally:
            try:
                client.close()
            except Exception:
                pass
except Exception as e:
    print("Fatal:", repr(e))
finally:
    try:
        srv.close()
    except Exception:
        pass

