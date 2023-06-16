"""Module with functionality for listening to events."""
from typing import Iterator, Optional, Tuple

from absl import logging
from inductiva_api.events import parse
from inductiva_api.events.schemas import Event
from redis import Redis


class EventSource:
    """Class for listening to events from Redis streams."""

    def __init__(self,
                 stream: str,
                 redis_hostname: str,
                 redis_port: int,
                 consumer_group: Optional[str] = None,
                 consumer_name: Optional[str] = None) -> None:
        self._conn = Redis(
            redis_hostname,
            redis_port,
            retry_on_timeout=True,
            decode_responses=True,
        )
        self._stream = stream
        self._consumer_group = consumer_group
        self._consumer_name = consumer_name
        self._use_consumer_group = not (consumer_group is None or
                                        consumer_name is None)
        logging.info("Using consumer group: %s", self._use_consumer_group)

        if consumer_group is None and consumer_name is not None:
            raise ValueError("A `consumer_group` must be provided if \
                      `consumer_name` is provided.")

        if consumer_name is None and consumer_group is not None:
            raise ValueError("A `consumer_name` must be provided if \
                    `consumer_group` is provided.")

    def _read_stream(self, last_id: str, sleep_ms=0):
        if self._use_consumer_group:
            return self._conn.xreadgroup(
                self._consumer_group,
                self._consumer_name,
                {self._stream: last_id},
                count=1,
                block=sleep_ms,
            )
        else:
            return self._conn.xread(
                {self._stream: last_id},
                count=1,
                block=sleep_ms,
            )

    def monitor(self, start_id="0-0") -> Iterator[Tuple[Event, str]]:
        """Method to monitors a Redis stream.

        This method reads from a Redis stream, yielding the events one by one
        as they are received. It also returns the ID of the received event.

        Usage:
            for event, event_id in event_source.monitor():
                # Do something with the event
                fun(event, event_id)

        Args:
            start_id: ID of the first event to read. If not provided, the
                first event of the stream will be read.

        Yields:
            Tuple with the event and the ID of the event in the Redis stream.
        """
        last_id = start_id
        while True:
            try:
                resp = self._read_stream(last_id)

                if resp:
                    _, messages = resp[0]
                    last_id, data = messages[0]

                    event = parse.from_dict(data)

                    yield event, last_id

                    if self._use_consumer_group:
                        self._conn.xack(
                            self._stream,
                            self._consumer_group,
                            last_id,
                        )

            except ConnectionError:
                logging.exception("Error in Redis connection")
