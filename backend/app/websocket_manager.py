from typing import Dict, List
from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {
            "entry": [],
            "exit": [],
        }

    async def connect(self, channel: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.setdefault(channel, []).append(websocket)

    def disconnect(self, channel: str, websocket: WebSocket):
        if websocket in self.active_connections.get(channel, []):
            self.active_connections[channel].remove(websocket)

    async def broadcast(self, channel: str, data: dict):
        dead = []
        for ws in self.active_connections.get(channel, []):
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(channel, ws)


manager = ConnectionManager()
