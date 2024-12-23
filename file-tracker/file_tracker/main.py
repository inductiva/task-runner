import asyncio
import logging
import os

from connection_manager import ConnectionManager
from task_listener import TaskListener


async def main():
    workdir = os.getenv("WORKDIR", "/workdir")
    os.chdir(workdir)

    connection_manager = ConnectionManager.from_env()
    file_tracker_host = os.getenv("FILE_TRACKER_HOST", "0.0.0.0")
    file_tracker_port = int(os.getenv("FILE_TRACKER_PORT", "5000"))
    task_listener = TaskListener(connection_manager, file_tracker_host,
                                 file_tracker_port)
    logging.info("Starting task listener")
    await task_listener.start()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
