"""Module with functionality for listening to events."""
from typing import Iterator, Optional, Tuple

import redis
from absl import logging

from inductiva_api.events import parse
from inductiva_api.events.schemas import Event


class RedisStreamEventSource:
    """Class for listening to events from Redis streams."""

    def __init__(
        self,
        redis_conn: redis.Redis,
        stream: str,
        consumer_group: Optional[str] = None,
        consumer_name: Optional[str] = None,
    ) -> None:
        self._conn = redis_conn
        self._stream = stream
        self._consumer_group = consumer_group
        self._consumer_name = consumer_name
        self._use_consumer_group = not (consumer_group is None or
                                        consumer_name is None)

        if consumer_group is None and consumer_name is not None:
            raise ValueError("A `consumer_group` must be provided if \
                      `consumer_name` is provided.")

        if consumer_name is None and consumer_group is not None:
            raise ValueError("A `consumer_name` must be provided if \
                    `consumer_group` is provided.")

    def _monitor_with_groups(self,
                             start_id="0",
                             sleep_ms=0) -> Iterator[Tuple[Event, str]]:
        """Monitor Redis stream using consumer groups.

        If the provided start_id is different from ">", the history of
        unacknowledged events will be processed first. This is useful when
        restarting the service, as it will process all events that were
        unacknowledged when the service was stopped.
        More info here:
         - https://redis.io/docs/data-types/streams-tutorial/#consumer-groups
        """
        UNDELIVERED_EVENTS_SPECIAL_ID = ">"  # noqa: N806
        checking_backlog = start_id != UNDELIVERED_EVENTS_SPECIAL_ID
        last_id = start_id

        while True:
            try:
                # If the backlog (history of unacknowledged events) has been
                # fully processed, use the special ">" ID to read undelivered
                # events.
                read_id = last_id if checking_backlog \
                    else UNDELIVERED_EVENTS_SPECIAL_ID

                resp = self._conn.xreadgroup(
                    self._consumer_group,
                    self._consumer_name,
                    {self._stream: read_id},
                    count=1,
                    block=sleep_ms,
                )

                if resp:
                    _stream_name, messages = resp[0]  # noqa: F841

                    # This means that there are no more unacknowledged events,
                    # so we can start reading new events using the special ">"
                    # ID.
                    if len(messages) == 0:
                        checking_backlog = False
                        continue

                    last_id, data = messages[0]

                    event = parse.from_dict(data)

                    yield event, last_id

                    self._conn.xack(self._stream, self._consumer_group, last_id)

            except ConnectionError:
                logging.exception("Error in Redis connection")

    def _monitor(self, start_id="0", sleep_ms=0) -> Iterator[Tuple[Event, str]]:
        """Monitor a Redis stream without using consumer groups."""
        last_id = start_id
        while True:
            try:
                resp = self._conn.xread(
                    {self._stream: last_id},
                    count=1,
                    block=sleep_ms,
                )

                if resp:
                    # Get contents from the first (and only) stream read.
                    _stream_name, messages = resp[0]  # noqa: F841

                    # Get only message from messages list (there's only one
                    # because we're reading with count=1).
                    last_id, data = messages[0]

                    event = parse.from_dict(data)

                    yield event, last_id

            except ConnectionError:
                logging.exception("Error in Redis connection")

    def monitor(self, start_id="0", sleep_ms=0) -> Iterator[Tuple[Event, str]]:
        """Method to monitor a Redis stream.

        This method reads from a Redis stream, yielding the events one by one
        as they are received. It also returns the ID of the received event.

        If a start_id is not provided, the stream will be read from the
        beginning if consumer groups are not being used. If not provided and
        consumer groups are being used, the events that have been delivered to
        the consumer but not acknowledged will be read, and after that, events
        that haven't been delivered will be read.

        Usage:
            for event, event_id in event_source.monitor():
                # Do something with the event
                fun(event, event_id)

        Args:
            start_id: ID to use when reading the first event. Default is "0".
                Note that Redis stream IDs are monotonically increasing, so the
                first event that will be read is the first event with an ID
                greater than the provided start_id. By using 0 as the default,
                the stream will be read from the beginning.

        Yields:
            Tuple with the event and the ID of the event in the Redis stream.
        """

        if self._use_consumer_group:
            yield from self._monitor_with_groups(start_id, sleep_ms)
        else:
            yield from self._monitor(start_id, sleep_ms)
