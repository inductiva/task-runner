import asyncio
import logging
import os

import aiohttp
from client_connection import ClientConnection

import file_tracker


class ConnectionManager:

    def __init__(self, signaling_server, user_api_key, ice_url):
        self._signaling_server = signaling_server
        self._user_api_key = user_api_key
        self._ice_url = ice_url
        self._headers = {
            "User-Agent": file_tracker.get_api_agent(),
            "X-API-Key": self._user_api_key
        }
        self.loop = None
        self.connections = []
        self._block_s = 1

    @classmethod
    def from_env(cls):
        return cls(
            signaling_server=os.getenv("API_URL", "https://api.inductiva.ai"),
            user_api_key=os.getenv("USER_API_KEY"),
            ice_url=os.getenv("ICE_URL", "webrtc.inductiva.ai:3478"),
        )

    async def listen(self, task_id):
        self.connections = []
        self.loop = asyncio.create_task(self._listen_loop(task_id))

    def _request_data(self, task_id, receiver_id=None, type=None, sdp=None):
        return {
            "sender_id": task_id,
            "receiver_id": receiver_id,
            "type": type,
            "sdp": sdp,
        }

    async def _listen_loop(self, task_id):
        url = f"{self._signaling_server}/tasks/{task_id}/"
        register_url = url + "register"
        message_url = url + f"message?client={task_id}&block_s={self._block_s}"
        offer_url = url + "offer"

        async with aiohttp.ClientSession() as session:
            await session.post(
                register_url,
                json=self._request_data(task_id),
                headers=self._headers,
            )

            while True:
                logging.info("Listening for connections")

                async with session.get(
                        message_url,
                        headers=self._headers,
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()

                        if data['type'] == 'offer':
                            client_connection = ClientConnection(
                                task_id, self._ice_url)

                            pc = await client_connection.setup_connection(data)

                            await session.post(
                                offer_url,
                                json=self._request_data(
                                    task_id,
                                    receiver_id=data['sender_id'],
                                    type='answer',
                                    sdp=pc.localDescription.sdp),
                                headers=self._headers,
                            )

                            self.connections.append(client_connection)

                    elif resp.status == 204:
                        logging.info("No messages.")
                        await asyncio.sleep(10)

                    else:
                        logging.error("Failed to get messages: %s", await
                                      resp.text())
                        await asyncio.sleep(30)

    async def close(self):
        if self.loop:
            self.loop.cancel()
        for connection in self.connections:
            await connection.close()
        logging.info("Connection manager closed")
