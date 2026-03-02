import digitalio
import board
import threading
from adafruit_pn532.spi import PN532_SPI
from time import sleep

# Standard NFC Forum NDEF Key A used by NFC Tools and most apps when
# writing NDEF to MIFARE Classic cards.
_MIFARE_KEY_A    = 0x60
_MIFARE_NDEF_KEY = bytes([0xD3, 0xF7, 0xD3, 0xF7, 0xD3, 0xF7])


# ── NDEF parsers (shared) ─────────────────────────────────────────────────────

def _parse_ndef_tlv(data: bytes) -> str | None:
    """Scan raw tag memory for an NDEF Message TLV and return its text payload."""
    i = 0
    while i < len(data) - 1:
        tlv_type = data[i]
        if tlv_type == 0x00:            # Null TLV — skip
            i += 1
            continue
        if tlv_type == 0xFE:            # Terminator TLV — stop
            break
        if data[i + 1] == 0xFF:         # 3-byte length
            if i + 3 >= len(data):
                break
            length        = (data[i + 2] << 8) | data[i + 3]
            payload_start = i + 4
        else:                           # 1-byte length
            length        = data[i + 1]
            payload_start = i + 2
        if tlv_type == 0x03:            # NDEF Message TLV
            return _parse_ndef_text(bytes(data[payload_start: payload_start + length]))
        i = payload_start + length
    return None


def _parse_ndef_text(ndef: bytes) -> str | None:
    """Parse the first NDEF record; return its text if it is a Well-Known Text record."""
    if len(ndef) < 3:
        return None
    header   = ndef[0]
    tnf      = header & 0x07
    sr       = bool(header & 0x10)   # Short Record
    il       = bool(header & 0x08)   # ID Length present
    type_len = ndef[1]
    offset   = 2

    if sr:
        payload_len = ndef[offset]
        offset += 1
    else:
        if offset + 4 > len(ndef):
            return None
        payload_len = int.from_bytes(ndef[offset:offset + 4], 'big')
        offset += 4

    if il:
        if offset >= len(ndef):
            return None
        offset += 1 + ndef[offset]     # skip ID length byte + ID

    if offset + type_len > len(ndef):
        return None
    record_type  = ndef[offset:offset + type_len]
    offset      += type_len
    payload      = ndef[offset:offset + payload_len]

    # TNF 0x01 Well-Known, Type 'T' → Text record
    if tnf == 0x01 and record_type == b'T' and len(payload) > 1:
        status   = payload[0]
        lang_len = status & 0x3F
        encoding = 'utf-16-be' if status & 0x80 else 'utf-8'
        return payload[1 + lang_len:].decode(encoding).strip()

    return None


# ── Card-type-specific readers ────────────────────────────────────────────────

def _read_ntag_ndef(pn532) -> str | None:
    """Read NDEF text from an NTAG2xx card (7-byte UID, pages 4–15)."""
    try:
        data = bytearray()
        for page in range(4, 16):
            block = None
            for _ in range(3):          # retry up to 3× for transient RF errors
                block = pn532.ntag2xx_read_block(page)
                if block is not None:
                    break
            if block is None:
                print(f"  NTAG: page {page} unreadable after 3 retries")
                break
            data.extend(block)
        print(f"  NTAG: read {len(data)} bytes — {data[:8].hex()!r}...")
        return _parse_ndef_tlv(bytes(data))
    except Exception as e:
        print(f"NTAG NDEF read error: {e}")
    return None


def _read_mifare_classic_ndef(pn532, uid: bytes) -> str | None:
    """Read NDEF text from a MIFARE Classic card (4-byte UID).

    NDEF data begins at sector 1 (block 4). Each sector has 4 blocks;
    the last block of every sector is the sector trailer and is skipped.
    Authentication uses the standard NFC Forum NDEF Key A.
    """
    try:
        data = bytearray()
        for sector in range(1, 5):      # sectors 1–4 → ~192 bytes, enough for any ID
            block_start = sector * 4
            ok = pn532.mifare_classic_authenticate_block(
                uid, block_start, _MIFARE_KEY_A, _MIFARE_NDEF_KEY
            )
            print(f"  MIFARE: sector {sector} auth {'OK' if ok else 'FAILED'}")
            if not ok:
                break
            for block in range(block_start, block_start + 3):  # skip trailer (+3)
                block_data = pn532.mifare_classic_read_block(block)
                print(f"  MIFARE: block {block} = {block_data.hex() if block_data else None}")
                if block_data is None:
                    break
                data.extend(block_data)
        return _parse_ndef_tlv(bytes(data))
    except Exception as e:
        print(f"MIFARE Classic NDEF read error: {e}")
    return None


def _read_ndef_text(pn532, uid: bytes) -> str | None:
    """Dispatch to the correct NDEF reader based on card UID length.

    4-byte UID → MIFARE Classic
    7-byte UID → NTAG2xx
    """
    if len(uid) == 4:
        return _read_mifare_classic_ndef(pn532, uid)
    return _read_ntag_ndef(pn532)


# ── NFCMonitor ────────────────────────────────────────────────────────────────

class NFCMonitor:
    def __init__(self, on_card_detected):
        self.on_card_detected = on_card_detected

        self.thread     = None
        self.stop_flag  = threading.Event()
        self.last_uid   = None
        self.card_present    = False
        self.no_card_count   = 0
        self.no_card_threshold = 3

        spi = board.SPI()
        cs  = digitalio.DigitalInOut(board.D7)  # GPIO7, physical pin 26
        self.pn532 = PN532_SPI(spi, cs, reset=None, debug=False)
        try:
            ic, ver, rev, support = self.pn532.firmware_version
            print(f"PN532 initialized: PN5{ic:02x} Firmware {ver}.{rev}")
        except Exception as e:
            print(f"Failed to initialize PN532: {e}")
            import sys
            sys.exit(1)
        self.pn532.SAM_configuration()

    def _detect(self, uid: bytes, uid_str: str):
        album_id = _read_ndef_text(self.pn532, uid)
        print(f"card detected: uid={uid_str} album_id={album_id!r}")
        self.on_card_detected(uid_str, album_id)

    def monitor_loop(self):
        while not self.stop_flag.is_set():
            try:
                uid = self.pn532.read_passive_target(timeout=0.1)
                if uid:
                    uid_str = "".join("{:02X}".format(b) for b in uid)
                    if not self.card_present:
                        self.card_present  = True
                        self.last_uid      = uid_str
                        self.no_card_count = 0
                        self._detect(uid, uid_str)
                    elif uid_str != self.last_uid:
                        self.last_uid = uid_str
                        self._detect(uid, uid_str)
                    else:
                        self.no_card_count = 0
                else:
                    if self.card_present:
                        self.no_card_count += 1
                        if self.no_card_count >= self.no_card_threshold:
                            self.card_present  = False
                            self.last_uid      = None
                            self.no_card_count = 0
                    else:
                        self.no_card_count = 0

                sleep(0.3 if self.card_present else 0.1)

            except Exception as e:
                print(f"❌ NFC polling error: {e}")
                sleep(1)

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        self.stop_flag.clear()
        self.thread = threading.Thread(target=self.monitor_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_flag.set()
        if self.thread:
            self.thread.join()
