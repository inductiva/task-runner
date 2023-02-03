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


def monitor_redis_stream(redis_connection,
                         stream_name,
                         request_handler: TaskRequestHandler,
                         last_stream_id=0):
    """Monitors Redis stream, calling a callback to handle requests.

    Args:
        redis_connection: Connection to Redis server
        stream_name: Name of Redis Stream.
        request_handler: TaskRequestHandler instance that will handle
            the received request.
        last_id: Unique id of the stream item you want to start
            listing from (every item after that will be logged).
            Redis stream ids are sorted, based on timestamps.
            Default: 0 (will log the whole stream).

    """
    sleep_ms = 0  # 0ms means block forever

    while True:
        try:
            resp = redis_connection.xread(
                {stream_name: last_stream_id},
                count=1,  # reads one item at a time.
                block=sleep_ms)
            if resp:
                _, messages = resp[0]
                last_stream_id, request = messages[0]

                logging.info("REDIS ID: %s", str(last_stream_id))
                logging.info("      --> %s", str(request))

                request_handler(request)

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
        request_handler=request_handler,
    )


if __name__ == "__main__":
    logging.set_verbosity(logging.INFO)
    logging.info("hello")
    app.run(main)
