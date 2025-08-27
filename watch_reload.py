# watch_reload.py
import importlib, sys, os, traceback
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class ReloadOnChange(FileSystemEventHandler):
    def __init__(self, module_name, file_path, on_reload=None):
        self.module_name = module_name
        self.file_path = os.path.abspath(file_path)
        self.on_reload = on_reload
        if module_name not in sys.modules:
            spec = importlib.util.spec_from_file_location(module_name, self.file_path)
            m = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(m)  # type: ignore
            sys.modules[module_name] = m
        self.module = sys.modules[module_name]

    def on_modified(self, event):
        if os.path.abspath(event.src_path) != self.file_path:
            return
        try:
            self.module = importlib.reload(self.module)
            if self.on_reload:
                self.on_reload(self.module)
            print(f"[watchdog] reloaded {self.module_name}")
        except Exception:
            print("[watchdog] reload failed; keeping old module")
            traceback.print_exc()

def start_watch(module_name, file_path, on_reload=None):
    handler = ReloadOnChange(module_name, file_path, on_reload)
    obs = Observer()
    obs.schedule(handler, os.path.dirname(file_path) or ".", recursive=False)
    obs.start()
    return obs, handler
