import os
from functools import lru_cache
from pydantic import BaseModel
import redis

class Settings(BaseModel):
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    node_id: str = os.getenv("NODE_ID", "node-local")

@lru_cache
def get_settings() -> Settings:
    return Settings()

@lru_cache
def get_redis():
    return redis.from_url(get_settings().redis_url, decode_responses=True)
