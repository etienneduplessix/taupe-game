import asyncio
import json
from typing import Dict, Set
from fastapi import WebSocket
import redis.asyncio as redis
from config import settings

class WebSocketManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
        self.pubsub = self.redis_client.pubsub()

    async def connect(self, user_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[user_id] = websocket
        print(f"✓ User {user_id} connected. Total: {len(self.active_connections)}")

    def disconnect(self, user_id: str):
        if user_id in self.active_connections:
            del self.active_connections[user_id]
            print(f"✗ User {user_id} disconnected. Total: {len(self.active_connections)}")

    async def send_personal_message(self, message: dict, user_id: str):
        if user_id in self.active_connections:
            try:
                await self.active_connections[user_id].send_json(message)
            except Exception as e:
                print(f"⚠️  Error sending to {user_id}: {e}")

    async def broadcast(self, message: dict):
        # Send directly to local connections AND publish via Redis for multi-worker
        print(f"📤 Broadcasting {message.get('type')} to {len(self.active_connections)} local clients")
        for user_id, connection in list(self.active_connections.items()):
            try:
                await connection.send_json(message)
            except Exception as e:
                print(f"⚠️  Error sending to {user_id}: {e}")
        try:
            await self.redis_client.publish("game_events", json.dumps(message))
        except Exception as e:
            print(f"⚠️  Redis publish failed (non-fatal): {e}")

    async def listen_for_events(self):
        try:
            print("🔴 Redis listener starting...")
            await self.pubsub.subscribe("game_events")
            print("🟢 Redis listener subscribed to game_events")
            async for message in self.pubsub.listen():
                if message["type"] == "message":
                    # Already sent directly in broadcast(), this is for multi-worker support
                    pass
        except Exception as e:
            print(f"❌ Redis listener error: {e}")

ws_manager = WebSocketManager()
