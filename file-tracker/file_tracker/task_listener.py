import asyncio
import logging

SERVER_HOST = "0.0.0.0"
SERVER_PORT = 5000


class TaskListener:

    def __init__(self, task_coordinator, host=SERVER_HOST, port=SERVER_PORT):
        self.task_coordinator = task_coordinator
        self.host = host
        self.port = port

    async def start(self):
        server = await asyncio.start_server(self._handler, self.host, self.port)
        logging.info("Task listener started on %s:%s", self.host, self.port)
        async with server:
            await server.serve_forever()
        logging.info("Task listener stopped")

    async def _handler(self, reader, writer):
        data = await reader.read(1024)
        message = data.decode()
        logging.info("New task: %s", message)

        if message.startswith("start:"):
            task_id = message.split(":")[1]
            await self.task_coordinator.listen(task_id)
        elif message.startswith("stop:"):
            task_id = message.split(":")[1]
            await self.task_coordinator.close()
        else:
            logging.error("Unknown message: %s", message)

        # Send a response back to the client
        writer.write(b"ACK")
        await writer.drain()

        # Close the connection
        writer.close()
        await writer.wait_closed()
