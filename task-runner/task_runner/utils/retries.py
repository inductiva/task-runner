"""Utils for error handling and retries."""
import functools
import time

from absl import logging


def retry(exceptions=Exception, delay=1, max_tries=-1, backoff=1):
    """Decorator that retries a function if it raises an exception.

    Args:
        exceptions: Exception or tuple of exceptions to catch.
        delay: Initial delay between retries in seconds.
        max_tries: Maximum number of retries. -1 means infinite retries.
        backoff: Multiplier applied to delay between retries.

    Raises:
        If the function raises an exception on the last try, it will be
        propagated.
    """

    def decorator(func):

        @functools.wraps(func)
        def _retry(*args, **kwargs):
            tries = 0
            cur_delay = delay

            while max_tries == -1 or tries < max_tries:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    tries += 1

                    if tries == max_tries:
                        raise

                    logging.warning(
                        "Caught exception: %s. "
                        "Try %s/%s. Retrying in %s seconds...",
                        repr(e),
                        tries,
                        'inf' if max_tries == -1 else max_tries,
                        cur_delay,
                    )

                    time.sleep(cur_delay)

                    cur_delay *= backoff

        return _retry

    return decorator
