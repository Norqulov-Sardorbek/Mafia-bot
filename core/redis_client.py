import redis.asyncio as redis
from decouple import config

REDIS_HOST = config("REDIS_HOST", "redis")
REDIS_PORT = int(config("REDIS_PORT", 6379))

redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    decode_responses=True
)
