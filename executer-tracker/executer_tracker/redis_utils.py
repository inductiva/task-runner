"""Methods to interact with Redis server."""
from absl import logging
from redis import Redis


def create_redis_connection(redis_hostname, redis_port):
    redis_conn = Redis(
        redis_hostname,
        redis_port,
        retry_on_timeout=True,
        decode_responses=True,
    )

    return redis_conn


def delete_redis_consumer(redis_hostname, redis_port, stream, consumer_group,
                          consumer_name):
    logging.info("Deleting \"%s\" from group \"%s\" in stream \"%s\"...",
                 consumer_name, consumer_group, stream)
    conn = create_redis_connection(redis_hostname, redis_port)
    conn.xgroup_delconsumer(stream, consumer_group, consumer_name)
    logging.info("Deletion successful.")
