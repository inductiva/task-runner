import json
import logging

from aiortc import (
    RTCConfiguration,
    RTCIceServer,
    RTCPeerConnection,
    RTCSessionDescription,
)
from file_operations import ls, tail

# STUN/TURN server configuration
#
ICE_SERVERS = [
    RTCIceServer("stun:34.79.246.4:3478"),
    RTCIceServer("turn:34.79.246.4:3478")
]


class ClientConnection:

    def __init__(self, task_id, ice_servers=ICE_SERVERS):
        self.pc = RTCPeerConnection(RTCConfiguration(iceServers=ice_servers))
        self.path = task_id + "/output/artifacts/"

    async def setup_connection(self, data):

        @self.pc.on("datachannel")
        def on_datachannel(channel):

            @channel.on("message")
            async def on_message(message):
                if message == "ls":
                    contents = await ls(self.path)
                    channel.send(json.dumps(contents))

                elif message.startswith("tail:"):
                    filename = message.split(":")[1]
                    content = await tail(self.path + filename)
                    channel.send(json.dumps(content))

            @channel.on("close")
            async def on_close():
                await self.close()
                logging.info("PeerConnection closed")

        await self.pc.setRemoteDescription(
            RTCSessionDescription(sdp=data['sdp'], type=data['type']))
        answer = await self.pc.createAnswer()
        await self.pc.setLocalDescription(answer)

        return self.pc

    async def close(self):
        await self.pc.close()
