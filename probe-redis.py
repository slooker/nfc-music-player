from env import load_env
from kv_lookup import RedisClient
import os

load_env()
rc = RedisClient(
    host=os.getenv("REDIS_HOST","192.168.0.66"),
    port=int(os.getenv("REDIS_PORT","6379")),
    password=os.getenv("REDIS_PASSWORD"),
    username=os.getenv("REDIS_USER"),  # may be None
)
print("GET 42E35CAE =>", rc.get("42E35CAE"))

