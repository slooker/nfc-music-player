import os
import queue
import threading
import time

class CSVWatcher:
    def __init__(self, watch_file):
        self.last_modified_csv_time = 0
        self.stop_event = threading.Event()
        self.csv_thread = None
        self.csv_changed_queue = queue.Queue()
        self.watch_file = watch_file

    def _watch_csv_loop(self):
        """Thread loop that checks for CSV changes every 10 seconds"""
        while not self.stop_event.is_set():
            try:
                current_modified_time = os.path.getmtime(self.watch_file)
                if current_modified_time != self.last_modified_csv_time:
                    print("CSV is changed!")
                    self.last_modified_csv_time = current_modified_time
                    self.csv_changed_queue.put(True)
                else:
                    #print("CSV is not changed")
                    self.csv_changed_queue.put(False)
            except FileNotFoundError:
                print("CSV file not found!")
            # Sleep in small increments so we can exit quickly
            for _ in range(10):
                if self.stop_event.is_set():
                    break
                time.sleep(1)

        print("CSV watcher thread stopping...")

    def start(self):
        if self.csv_thread is None or not self.csv_thread.is_alive():
            print("Starting CSV watcher thread")
            self.csv_thread = threading.Thread(target=self._watch_csv_loop, daemon=True)
            self.csv_thread.start()
        return self.csv_changed_queue

    def stop(self):
        print("Stopping CSV watcher thread...")
        self.stop_event.set()
        if self.csv_thread:
            self.csv_thread.join()
        print("CSV watcher stopped.")