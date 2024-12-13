import logging
import os

from aiortc import (
    RTCConfiguration,
    RTCIceServer,
    RTCPeerConnection,
    RTCSessionDescription,
)
from file_operations import OperationError, ls, tail
from operation_response import OperationResponse, OperationStatus


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
        self.path = os.path.join(task_id, "output", "artifacts")

    async def setup_connection(self, data):

        @self.pc.on("datachannel")
        def on_datachannel(channel):

            @channel.on("message")
            async def on_message(message):
                response = OperationResponse()
                try:
                    if message == "ls":
                        response.message = ls(self.path)

                    elif message.startswith("tail:"):
                        filename = message.split(":")[1]
                        response.message = tail(
                            os.path.join(self.path, filename))
                    else:
                        response = OperationResponse(
                            status=OperationStatus.INVALID,
                            message="Unknown command")
                except OperationError as e:
                    response = OperationResponse(status=OperationStatus.ERROR,
                                                 message=str(e))
                finally:
                    channel.send(response.to_json_string())

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
