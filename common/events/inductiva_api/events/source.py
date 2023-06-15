"""Module with functionality for listening to events."""
from typing import Iterator, Tuple

from absl import logging
from inductiva_api.events import parse
from inductiva_api.events.schemas import Event
from redis import Redis


class EventSource:
    """Class for listening to events from Redis streams."""

    def __init__(self, stream: str, redis_hostname: str,
                 redis_port: int) -> None:
        self._conn = Redis(
            redis_hostname,
            redis_port,
            retry_on_timeout=True,
            decode_responses=True,
        )
        self._stream = stream

    def monitor(self, start_id="0-0") -> Iterator[Tuple[Event, str]]:
        last_id = start_id
        while True:
            try:
                resp = self._conn.xread(
                    {self._stream: last_id},
                    count=1,
                )
                if resp:
                    _, messages = resp[0]
                    last_id, data = messages[0]

                    event = parse.from_dict(data)

                    yield event, last_id

            except ConnectionError:
                logging.exception("Error in Redis connection")
