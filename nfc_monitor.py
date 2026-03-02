import digitalio
import board
import threading
from adafruit_pn532.spi import PN532_SPI
from time import sleep


def _read_ndef_text(pn532) -> str | None:
    """Read an NDEF Text record from an NTAG2xx card.

    Reads user-data pages 4–15 (48 bytes) and parses the NDEF TLV structure.
    Returns the text payload string, or None if no Text record is found.
    """
    try:
        data = bytearray()
        for page in range(4, 16):
            block = None
            for _ in range(3):
                block = pn532.ntag2xx_read_block(page)
                if block is not None:
                    break
            if block is None:
                break
            data.extend(block)

        i = 0
        while i < len(data) - 1:
            tlv_type = data[i]
            if tlv_type == 0x00:        # Null TLV — skip single byte
                i += 1
                continue
            if tlv_type == 0xFE:        # Terminator TLV — stop
                break
            # Length field: 0xFF prefix means 3-byte length
            if data[i + 1] == 0xFF:
                if i + 3 >= len(data):
                    break
                length = (data[i + 2] << 8) | data[i + 3]
                payload_start = i + 4
            else:
                length = data[i + 1]
                payload_start = i + 2
            if tlv_type == 0x03:        # NDEF Message TLV
                return _parse_ndef_text(bytes(data[payload_start: payload_start + length]))
            i = payload_start + length
    except Exception as e:
        print(f"NDEF read error: {e}")
    return None


def _parse_ndef_text(ndef: bytes) -> str | None:
    """Parse the first NDEF record and return its text payload.

    Handles Well-Known Text records (TNF=0x01, Type=b'T') only.
    """
    if len(ndef) < 3:
        return None
    header    = ndef[0]
    tnf       = header & 0x07
    sr        = bool(header & 0x10)   # Short Record flag
    il        = bool(header & 0x08)   # ID Length flag present
    type_len  = ndef[1]
    offset    = 2

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
        id_len  = ndef[offset]
        offset += 1 + id_len

    if offset + type_len > len(ndef):
        return None
    record_type = ndef[offset:offset + type_len]
    offset     += type_len
    payload     = ndef[offset:offset + payload_len]

    # TNF 0x01 Well-Known, Type 'T' → Text record
    if tnf == 0x01 and record_type == b'T' and len(payload) > 1:
        status   = payload[0]
        lang_len = status & 0x3F
        encoding = 'utf-16-be' if status & 0x80 else 'utf-8'
        return payload[1 + lang_len:].decode(encoding).strip()

    return None


class NFCMonitor:
    def __init__(self, on_card_detected):
        self.on_card_detected = on_card_detected

        self.thread = None
        self.stop_flag = threading.Event()

        self.last_uid = None
        self.card_present = False
        self.no_card_count = 0
        self.no_card_threshold = 3  # consecutive misses before removal

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

    def _detect(self, uid_str: str):
        """Read NDEF text from the card and fire on_card_detected(uid_str, album_id)."""
        album_id = _read_ndef_text(self.pn532)
        print(f"card detected: uid={uid_str} album_id={album_id!r}")
        self.on_card_detected(uid_str, album_id)

    def monitor_loop(self):
        while not self.stop_flag.is_set():
            try:
                uid = self.pn532.read_passive_target(timeout=0.1)
                if uid:
                    uid_str = "".join("{:02X}".format(b) for b in uid)
                    if not self.card_present:
                        self.card_present = True
                        self.last_uid = uid_str
                        self.no_card_count = 0
                        self._detect(uid_str)
                    elif uid_str != self.last_uid:
                        self.last_uid = uid_str
                        self._detect(uid_str)
                    else:
                        self.no_card_count = 0
                else:
                    if self.card_present:
                        self.no_card_count += 1
                        if self.no_card_count >= self.no_card_threshold:
                            self.card_present = False
                            self.last_uid = None
                            self.no_card_count = 0
                    else:
                        self.no_card_count = 0

                if self.card_present:
                    sleep(0.3)
                else:
                    sleep(0.1)
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
