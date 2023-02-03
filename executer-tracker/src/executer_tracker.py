"""Main script for managing executers.

This script reads from a Redis stream, handling received requests
by launching the corresponding Python script.

Usage:
  python executer_tracker.py
"""
import os

from absl import app
from absl import flags
from absl import logging

from redis import Redis

from task_request_handler import TaskRequestHandler

FLAGS = flags.FLAGS

flags.DEFINE_string("redis_stream", "all_requests",
                    "Name of the Redis Stream to subscribe to.")
flags.DEFINE_string(
    "redis_consumer_group", "all_consumers",
    "Name of the consumer group to use when reading from Redis Stream.")
flags.DEFINE_string(
    "redis_consumer_name",
    None,
    "Unique name to use when reading from the consumer group.",
    required=True)

DELIVER_NEW_MESSAGES = ">"


def monitor_redis_stream(redis_connection, stream_name: str,
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
    sleep_ms = 0  # 0ms means block forever

    while True:
        try:
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
                _, messages = resp[0]
                stream_entry_id, request = messages[0]
                logging.info("REDIS ID: %s", str(stream_entry_id))
                logging.info("      --> %s", str(request))

                request_handler(request)

                # Acknowledge successful processing of the received message
                redis_connection.xack(consumer_name, consumer_group,
                                      stream_entry_id)

        except ConnectionError as e:
            logging.info("ERROR REDIS CONNECTION: %s", str(e))


def main(_):
    redis_hostname = os.getenv("REDIS_HOSTNAME")
    redis_port = os.getenv("REDIS_PORT", "6379")

    artifact_dest = os.getenv("ARTIFACT_STORE")  # drive shared with the Web API

    working_dir_root = os.path.join(os.path.abspath(os.sep), "working_dir")
    os.makedirs(working_dir_root, exist_ok=True)

    redis_conn = Redis(redis_hostname,
                       redis_port,
                       retry_on_timeout=True,
                       decode_responses=True)

    request_handler = TaskRequestHandler(
        redis_connection=redis_conn,
        artifact_dest=artifact_dest,
        working_dir_root=working_dir_root,
    )

    monitor_redis_stream(
        redis_connection=redis_conn,
        stream_name=FLAGS.redis_stream,
        consumer_group=FLAGS.redis_consumer_group,
        consumer_name=FLAGS.redis_consumer_name,
        request_handler=request_handler,
    )


if __name__ == "__main__":
    logging.set_verbosity(logging.INFO)
    app.run(main)
