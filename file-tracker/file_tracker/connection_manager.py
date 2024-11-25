import asyncio
import logging
import os

import aiohttp
from client_connection import ClientConnection

SIGNALING_SERVER = os.getenv("API_URL")
USER_API_KEY = os.getenv("USER_API_KEY")


class ConnectionManager:

    def __init__(self,):
        self._signaling_server = SIGNALING_SERVER
        self._user_api_key = USER_API_KEY
        self._headers = {"X-API-Key": self._user_api_key}

    async def listen(self, task_id):
        self.running = True
        self.connections = []
        asyncio.create_task(self._listen_loop(task_id))

    async def _listen_loop(self, task_id):
        async with aiohttp.ClientSession() as session:
            await session.post(f"{SIGNALING_SERVER}/tasks/{task_id}/register",
                               json={"clientId": task_id},
                               headers=self._headers)

            while self.running:
                logging.info("Listening for connections")
                async with session.get(
                        f"{SIGNALING_SERVER}/tasks/{task_id}/message?client={task_id}",
                        headers=self._headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data['type'] == 'offer':
                            client_connection = ClientConnection(task_id)
                            pc = await client_connection.setup_connection(data)
                            await session.post(
                                f"{SIGNALING_SERVER}/tasks/{task_id}/offer",
                                json={
                                    "receiverId": data['senderId'],
                                    "type": "answer",
                                    "sdp": pc.localDescription.sdp
                                },
                                headers=self._headers)
                            self.connections.append(client_connection)
                    else:
                        logging.error("Failed to get message: %s", resp.status)
                        logging.error(await resp.text())
                        await asyncio.sleep(10)
            logging.info("Stopped listening for messages")

    async def close(self):
        self.running = False
        for connection in self.connections:
            await connection.close()
