# probe_where.py
import sys, inspect
import kv_lookup

print("cwd:", __import__("os").getcwd())
print("sys.executable:", sys.executable)
print("sys.path[0]:", sys.path[0])
print("kv_lookup file:", kv_lookup.__file__)
print("RedisClient.__init__ args:",
      inspect.signature(kv_lookup.RedisClient.__init__))

