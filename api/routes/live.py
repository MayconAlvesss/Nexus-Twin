"""
NexusTwin: Real-time Telemetry Service 📡
========================================
WebSocket router for streaming SHI updates to connected clients/dashboards.
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import List
import logging
import asyncio
import json

logger = logging.getLogger(__name__)
router = APIRouter()

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"New client connected to Live Feed. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)

manager = ConnectionManager()

@router.websocket("/ws/telemetry/{element_id}")
async def websocket_endpoint(websocket: WebSocket, element_id: str):
    await manager.connect(websocket)
    try:
        # Simulate live data push loop
        while True:
            # TODO: Integrate with real database triggers or redis pub/sub
            # For now, we simulate a 'Heartbeat' with random sensor fluctuations
            data = {
                "element_id": element_id,
                "status": "LIVE",
                "shi_snapshot": 75.0, # Target: replace with dynamic value
                "timestamp": "2026-04-10T..."
            }
            await websocket.send_text(json.dumps(data))
            await asyncio.sleep(2) # 0.5Hz refresh rate
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info(f"Client disconnected from {element_id} feed")
