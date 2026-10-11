from fastapi import WebSocket
from typing import List, Dict, Any
import json
import logging

logger = logging.getLogger("vignan.websocket")

class WebSocketManager:
    """Manages active WebSocket connections to SOC dashboards and broadcasts live telemetry."""

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"[WebSocket] Client connected. Total clients: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"[WebSocket] Client disconnected. Remaining: {len(self.active_connections)}")

    async def broadcast(self, event_type: str, data: Dict[str, Any]):
        """Broadcasts a JSON envelope to all active dashboards."""
        if not self.active_connections:
            return

        payload = json.dumps({
            "event": event_type,
            "data": data
        })

        for connection in list(self.active_connections):
            try:
                await connection.send_text(payload)
            except Exception as e:
                logger.warning(f"[WebSocket] Error broadcasting to client: {e}")
                self.disconnect(connection)

ws_manager = WebSocketManager()
