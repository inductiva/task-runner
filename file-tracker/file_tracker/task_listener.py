import asyncio
import logging


class TaskListener:

    def __init__(self, task_coordinator, host, port):
        self.task_coordinator = task_coordinator
        self.host = host
        self.port = port
        self.server = None

    async def start(self):
        self.server = await asyncio.start_server(self._handler, self.host,
                                                 self.port)
        logging.info("Task listener started on %s:%s", self.host, self.port)
        try:
            async with self.server:
                await self.server.serve_forever()
        except asyncio.CancelledError:
            logging.info("Task listener stopped")
            pass

    async def _handler(self, reader, writer):
        data = await reader.read(1024)
        message = data.decode()
        server_terminate = False

        if message.startswith("start:"):
            task_id = message.split(":")[1]
            await self.task_coordinator.listen(task_id)
        elif message.startswith("stop:"):
            task_id = message.split(":")[1]
            await self.task_coordinator.close()
        elif message == "terminate":
            await self.task_coordinator.close()
            server_terminate = True
        else:
            logging.error("Unknown message: %s", message)

        # Send a response back to the client
        writer.write(b"ACK")
        await writer.drain()

        # Close the connection
        writer.close()
        await writer.wait_closed()

        if server_terminate:
            self.server.close()
            await self.server.wait_closed()
