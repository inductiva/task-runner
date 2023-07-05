"""Logging events to Redis."""
from redis.asyncio import Redis as AsyncRedis
from redis import Redis

from inductiva_api.events import parse
from inductiva_api.events.schemas import Event


class RedisStreamEventLogger:
    """Class that handles logging events to Redis."""

    def __init__(self, redis: AsyncRedis, stream_key: str):
        self.redis = redis
        self.stream_key = stream_key

    async def log(self, event: Event):
        return await self.redis.xadd(self.stream_key, parse.to_dict(event))


class RedisStreamEventLoggerSync:
    """Class that handles logging events to Redis."""

    def __init__(self, redis: Redis, stream_key: str):
        self.redis = redis
        self.stream_key = stream_key

    def log(self, event: Event):
        return self.redis.xadd(self.stream_key, parse.to_dict(event))
