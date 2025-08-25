# reloader.py
import importlib, importlib.util, sys, os, time, threading, traceback
from types import ModuleType
from typing import Optional, Callable

class FileModuleReloader:
    def __init__(self, module_name: str, file_path: str, interval: float = 0.5,
                 on_reload: Optional[Callable[[ModuleType], None]] = None, autostart=True):
        self.module_name = module_name
        self.file_path = os.path.abspath(file_path)
        self.interval = interval
        self.on_reload = on_reload
        self._stop = threading.Event()
        self._mt = None
        self.module = None
        self._import_initial()
        if autostart:
            self.start()

    def _stat_mtime(self):
        try:
            return os.stat(self.file_path).st_mtime_ns
        except FileNotFoundError:
            return None

    def _import_initial(self):
        self._mt = self._stat_mtime()
        if self.module_name in sys.modules:
            self.module = sys.modules[self.module_name]
        else:
            spec = importlib.util.spec_from_file_location(self.module_name, self.file_path)
            module = importlib.util.module_from_spec(spec)
            assert spec and spec.loader
            spec.loader.exec_module(module)
            sys.modules[self.module_name] = module
            self.module = module

    def _reload(self):
        try:
            self.module = importlib.reload(self.module)
            if self.on_reload:
                self.on_reload(self.module)
            print(f"[reloader] reloaded {self.module_name}")
        except Exception:
            print(f"[reloader] reload failed; keeping old module")
            traceback.print_exc()

    def _loop(self):
        while not self._stop.is_set():
            mt = self._stat_mtime()
            if mt is not None and self._mt is not None and mt > self._mt:
                self._mt = mt
                self._reload()
            time.sleep(self.interval)

    def start(self):
        self._thread = threading.Thread(target=self._loop, daemon=True, name=f"reloader:{self.module_name}")
        self._thread.start()

    def stop(self):
        self._stop.set()
        if hasattr(self, "_thread"):
            self._thread.join(timeout=1.0)
