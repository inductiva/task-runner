import asyncio
import logging
import os


class ApiFileTracker:

    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.started = False

    @classmethod
    def from_env(cls):
        return cls(
            host=os.getenv("FILE_TRACKER_HOST", "0.0.0.0"),
            port=int(os.getenv("FILE_TRACKER_PORT", "5000")),
        )

    def start(self, task_id):
        logging.info("Starting task streaming: %s", task_id)
        message = "start:" + task_id
        self.started = asyncio.run(self._message(message))

    def stop(self, task_id):
        if self.started:
            logging.info("Stoping task streaming: %s", task_id)
            message = "stop:" + task_id
            asyncio.run(self._message(message))
            self.started = False

    async def _message(self, message, num_retries=3):
        reader, writer = await asyncio.open_connection(self.host, self.port)
        while num_retries > 0:
            writer.write(message.encode())
            await writer.drain()

            data = await reader.read(100)
            response = data.decode()

            if response == "ACK":
                break

            num_retries -= 1
        writer.close()
        await writer.wait_closed()
        return num_retries > 0