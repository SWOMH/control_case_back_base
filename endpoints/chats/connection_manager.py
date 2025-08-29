from typing import Dict, Set
from fastapi import WebSocket
import asyncio


class ConnectionManager:
    """
    Хранит маппинг chat_id -> set(WebSocket)
    и user_id -> set(WebSocket) (опционально).
    """
    def __init__(self):
        self.chat_connections: Dict[int, Set[WebSocket]] = {}
        self.user_connections: Dict[int, Set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, chat_id: int, user_id: int, websocket: WebSocket):
        async with self._lock:
            conns = self.chat_connections.setdefault(chat_id, set())
            conns.add(websocket)
            uconns = self.user_connections.setdefault(user_id, set())
            uconns.add(websocket)

    async def disconnect(self, chat_id: int, user_id: int, websocket: WebSocket):
        async with self._lock:
            if chat_id in self.chat_connections:
                self.chat_connections[chat_id].discard(websocket)
                if not self.chat_connections[chat_id]:
                    del self.chat_connections[chat_id]
            if user_id in self.user_connections:
                self.user_connections[user_id].discard(websocket)
                if not self.user_connections[user_id]:
                    del self.user_connections[user_id]

    async def broadcast_to_chat(self, chat_id: int, message: dict):
        """
        Отправляет JSON-сообщение всем вебсокетам, подключённым к chat_id на этом инстансе.
        Не ставим await для каждой отправки по-очереди — собираем задачи.
        """
        conns = list(self.chat_connections.get(chat_id, []))
        if not conns:
            return
        data_text = message  # assuming dict; FastAPI WebSocket.json accepts dict via send_json
        tasks = [conn.send_json(data_text) for conn in conns]
        # Выполняем параллельно; игнорируем ошибки отдельных соединений
        await asyncio.gather(*tasks, return_exceptions=True)

    async def send_to_user(self, user_id: int, message: dict):
        conns = list(self.user_connections.get(user_id, []))
        if not conns:
            return
        tasks = [conn.send_json(message) for conn in conns]
        await asyncio.gather(*tasks, return_exceptions=True)
