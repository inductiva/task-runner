"""Methods to interact with Redis server."""
from redis import Redis
from absl import logging
from task_request_handler import TaskRequestHandler
from typing import Sequence

DELIVER_NEW_MESSAGES = ">"


def create_redis_connection(redis_hostname, redis_port):
    redis_conn = Redis(
        redis_hostname,
        redis_port,
        retry_on_timeout=True,
        decode_responses=True,
    )

    return redis_conn


def monitor_redis_stream(redis_connection, stream_names: Sequence[str],
                         consumer_group: str, consumer_name: str,
                         request_handler: TaskRequestHandler):
    """Monitors Redis stream, calling a callback to handle requests.

    The stream is read from via a consumer group. This requires that
    each executer reading from the stream has a name that is unique within
    the consumer group. Only one member of each consumer group receives
    a message, so this way only one executer handles each request.
    There's also an Ack response to notify the message as being
    successfully processed.

    Args:
        redis_connection: Connection to Redis server
        stream_name: Name of Redis Stream.
        consumer_group: Name of the consumer group.
        consumer_name: Name of the consumer: it should be
        request_handler: TaskRequestHandler instance that will handle
            the received request.
    """
    sleep_ms = 500  # 0ms means block forever

    logging.info("Starting monitoring of Redis streams:")
    for stream_name in stream_names:
        logging.info(" > %s", stream_name)

    while True:
        # Check each stream independently
        for stream_name in stream_names:
            try:
                logging.info("Waiting for requests on: %s", stream_name)
                resp = redis_connection.xreadgroup(
                    groupname=consumer_group,
                    consumername=consumer_name,
                    # Using the following ID will get messages that haven't
                    # been delivered to any consumer.
                    streams={stream_name: DELIVER_NEW_MESSAGES},
                    count=1,  # reads one item at a time.
                    block=sleep_ms,
                )
                if resp:
                    logging.info("Received request:")
                    logging.info("      --> %s", str(resp))
                    stream_name, messages = resp[0]
                    stream_entry_id, request = messages[0]
                    logging.info("REDIS ID: %s", str(stream_entry_id))
                    logging.info("      --> %s", str(request))

                    request_handler(request)

                    # Acknowledge successful processing of the received message
                    redis_connection.xack(stream_name, consumer_group,
                                          stream_entry_id)

            except ConnectionError as e:
                logging.info("ERROR REDIS CONNECTION: %s", str(e))


def delete_redis_consumer_multiple_streams(redis_hostname, redis_port,
                                           stream_names, consumer_group,
                                           consumer_name):
    for stream in stream_names:
        delete_redis_consumer(redis_hostname, redis_port, stream,
                              consumer_group, consumer_name)


def delete_redis_consumer(redis_hostname, redis_port, stream, consumer_group,
                          consumer_name):
    logging.info("Deleting \"%s\" from group \"%s\" in stream \"%s\"...",
                 consumer_name, consumer_group, stream)
    conn = create_redis_connection(redis_hostname, redis_port)
    conn.xgroup_delconsumer(stream, consumer_group, consumer_name)
    logging.info("Deletion successful.")
