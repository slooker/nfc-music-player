import digitalio
import board
import threading
from adafruit_pn532.spi import PN532_SPI
from time import sleep

class NFCMonitor:
    def __init__(self, on_card_detected, on_card_removed):
        self.on_card_detected = on_card_detected
        self.on_card_removed = on_card_removed

        self.thread = None
        self.stop_flag = threading.Event()

        self.last_uid = None
        self.card_present = False
        self.no_card_count = 0
        self.no_card_threshold = 3  # consecutive misses before removal
        # Initialize PN532 SPI
        spi = board.SPI()
        cs = digitalio.DigitalInOut(board.D7)  # GPIO8 CE0, physical pin 24
        self.pn532 = PN532_SPI(spi, cs, reset=None, debug=False)
        try:
            ic, ver, rev, support = self.pn532.firmware_version
            print(f"PN532 initialized: PN5{ic:02x} Firmware {ver}.{rev}")
        except Exception as e:
            print(f"Failed to initialize PN532: {e}")
            sys.exit(1)
        self.pn532.SAM_configuration()

    def pn532():
        return self.pn532

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
                        self.on_card_detected(uid_str)
                    elif uid_str != self.last_uid:
                        self.last_uid = uid_str
                        self.on_card_detected(uid_str)
                    else:
                        self.no_card_count = 0
                else:
                    if self.card_present:
                        self.no_card_count += 1
                        if self.no_card_count >= self.no_card_threshold:
                            self.card_present = False
                            self.last_uid = None
                            self.no_card_count = 0
                            self.on_card_removed()
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

