import json
import logging

from aiortc import (
    RTCConfiguration,
    RTCIceServer,
    RTCPeerConnection,
    RTCSessionDescription,
)
from file_operations import ls, tail


class ClientConnection:

    def __init__(self, task_id, ice_url):
        # STUN/TURN server configuration
        # ICE (Interactive Connectivity Establishment) server helps
        # establish a peer-to-peer connection by discovering and negotiating
        # network paths, including handling NAT traversal and firewall
        # issues, using STUN and TURN protocols.
        # https://developer.mozilla.org/en-US/docs/Web/API/WebRTC_API/Protocols
        ice_servers = [
            RTCIceServer(f"stun:{ice_url}"),
            RTCIceServer(f"turn:{ice_url}")
        ]
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
