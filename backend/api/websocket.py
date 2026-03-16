"""
api/websocket.py — WebSocket endpoint for real-time frontend updates

WebSocket URL: ws://localhost:8000/ws

Message types sent to frontend:
  - candle_update    : new 5-min candle data
  - position_update  : open position live P&L
  - signal           : new entry/exit signal
  - trade_complete   : trade closed with P&L
  - system_status    : mode, market status, capital
  - achievement      : newly earned achievement

All messages are JSON: { "type": "...", "data": {...} }

TODO (Step 12): Implement WebSocket handler below.
"""

from fastapi import WebSocket, WebSocketDisconnect
from typing import Any
import json


class ConnectionManager:
    """Manages active WebSocket connections."""

    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket) -> None:
        if ws in self.active:
            self.active.remove(ws)

    async def broadcast(self, message_type: str, data: Any) -> None:
        """Send a message to all connected clients."""
        payload = json.dumps({"type": message_type, "data": data})
        dead = []
        for ws in self.active:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    async def send_to(self, ws: WebSocket, message_type: str, data: Any) -> None:
        """Send a message to one specific client."""
        payload = json.dumps({"type": message_type, "data": data})
        await ws.send_text(payload)


# Global manager — import and use in scheduler / trader
manager = ConnectionManager()


async def websocket_endpoint(ws: WebSocket) -> None:
    """
    Main WebSocket handler.
    On connect: send current system state.
    On message: handle ping or client commands.
    On disconnect: clean up.

    TODO (Step 12): implement
    """
    await manager.connect(ws)
    try:
        while True:
            data = await ws.receive_text()
            msg = json.loads(data)
            if msg.get("type") == "ping":
                await manager.send_to(ws, "pong", {})
    except WebSocketDisconnect:
        manager.disconnect(ws)
