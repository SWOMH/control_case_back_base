from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from fastapi import status, Query
from typing import Optional
import json
import asyncio

from endpoints.chats.connection_manager import ConnectionManager
from endpoints.chats.redis_bridge import RedisPubSub
from utils.auth import get_current_user
from database.logic.chats.chat import chat_db


router = APIRouter()
manager = ConnectionManager()
# Создавать RedisPubSub один раз и хранить в app.state (инициализируется из main)
redis_pubsub: RedisPubSub | None = None

async def redis_message_callback(channel: str, payload: dict):
    """
    channel: 'chat:{chat_id}'
    payload: dict: {type, payload, meta}
    """
    # извлечь chat_id из канала
    if channel.startswith("chat:"):
        try:
            chat_id = int(channel.split(":", 1)[1])
        except Exception:
            return
        # рассылаем локально всем подключённым к этому чату
        await manager.broadcast_to_chat(chat_id, payload)
    else:
        # можно обработать другие каналы
        pass

# Функция инициализации (вызывать в main.on_event("startup"))
async def init_redis(pubsub_url: str):
    global redis_pubsub
    redis_pubsub = RedisPubSub(pubsub_url)
    await redis_pubsub.start(redis_message_callback)

@router.websocket("/ws/chat")
async def ws_chat_endpoint(websocket: WebSocket, token: str = Query(...), chat_id: Optional[int] = Query(None)):
    """
    Клиент подключается к /ws/chat?token=...&chat_id=123
    Если chat_id не передан — сервер попытается найти/создать активный чат для user.
    """
    # 1) авторизация
    user = await get_current_user(token)
    if not user:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # 2) получаем chat_id (если не передан)
    if chat_id is None:
        # если пользователь клиент/юзер: ищем активный чат, иначе ошибка
        existing = await chat_db.get_active_chat_by_user(user.id)
        if existing:
            chat_id = existing.id
        else:
            # можно разрешить отсутствие chat_id (тогда клиент должен создать чат REST-эндпоинтом)
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

    # 3) принимаем соединение
    await websocket.accept()

    # 4) локальное подключение
    await manager.connect(chat_id, user.id, websocket)

    # 5) подписка на Redis-канал для этого чата (если нужно)
    channel_name = f"chat:{chat_id}"
    await redis_pubsub.subscribe(channel_name)

    try:
        # опционально: при подключении можно послать backlog (через REST /chat/{id})
        await manager.send_to_user(user.id, {"type": "system", "payload": {"msg": "connected", "chat_id": chat_id}})

        while True:
            data_text = await websocket.receive_text()
            try:
                msg = json.loads(data_text)
            except Exception:
                # неправильный формат
                await websocket.send_json({"type": "error", "payload": {"msg": "invalid_json"}})
                continue

            # Обработка команд от клиента
            typ = msg.get("type")
            payload = msg.get("payload", {})

            if typ == "message":
                text = payload.get("text")
                # валидируем текст
                if text is None and not payload.get("attachments"):
                    await websocket.send_json({"type": "error", "payload": {"msg": "empty_message"}})
                    continue

                # сохраняем в БД (используй сессионный context manager)
                async with get_async_session() as session:
                    # add_message должен возвращать объект с полями id, chat_id, sender_id, sender_type, message, created_at
                    new_msg = await add_message(session, chat_id=chat_id, sender_id=user.id, sender_type=user.role.value, text=text)
                    # если есть вложения — их обычно загружают REST (в WebSocket можно отправлять base64, но не рекомендую)
                    # формируем событие для публикации
                    event = {
                        "type": "message",
                        "payload": {
                            "id": new_msg.id,
                            "chat_id": new_msg.chat_id,
                            "sender_id": new_msg.sender_id,
                            "sender_type": new_msg.sender_type,
                            "message": new_msg.message,
                            "created_at": new_msg.created_at.isoformat()
                        }
                    }
                    # публикуем в Redis (все инстансы получат и раскидают локально)
                    await redis_pubsub.publish(channel_name, event)

            elif typ == "read":
                upto = payload.get("upto_message_id")
                async with get_async_session() as session:
                    await mark_messages_read(session, chat_id=chat_id, reader_user_id=user.id, upto_message_id=upto)
                    event = {"type": "read", "payload": {"chat_id": chat_id, "user_id": user.id, "upto_message_id": upto}}
                    await redis_pubsub.publish(channel_name, event)

            elif typ == "typing":
                # typing broadcast to chat (no DB op)
                event = {"type": "typing", "payload": {"chat_id": chat_id, "user_id": user.id}}
                await redis_pubsub.publish(channel_name, event)

            elif typ == "transfer":
                # только support/manager может переводить
                if user.role.value not in ("support", "salesman"):
                    await websocket.send_json({"type": "error", "payload": {"msg": "forbidden"}})
                    continue
                new_support_id = payload.get("new_support_id")
                reason_id = payload.get("reason_id")
                async with get_async_session() as session:
                    chat = await transfer_chat(session, chat_id=chat_id, new_support_id=new_support_id, from_support_id=user.id, reason_id=reason_id)
                    event = {"type": "transfer", "payload": {"chat_id": chat_id, "new_support_id": new_support_id, "by": user.id}}
                    await redis_pubsub.publish(channel_name, event)

            elif typ == "close":
                # close chat
                if user.role.value not in ("support", "lawyer"):
                    await websocket.send_json({"type": "error", "payload": {"msg": "forbidden"}})
                    continue
                reason_id = payload.get("reason_id")
                async with get_async_session() as session:
                    chat = await close_chat(session, chat_id=chat_id, closed_by_user_id=user.id, reason_id=reason_id)
                    event = {"type": "close", "payload": {"chat_id": chat_id, "by": user.id}}
                    await redis_pubsub.publish(channel_name, event)

            else:
                await websocket.send_json({"type": "error", "payload": {"msg": "unknown_type"}})

    except WebSocketDisconnect:
        pass
    finally:
        # очистка: отключаем локальное соединение и отписываемся, если больше нет локальных подключений
        await manager.disconnect(chat_id, user.id, websocket)
        # если локально нет более соединений для этого чата — отписываемся от Redis (чтобы не засорять)
        if chat_id not in manager.chat_connections:
            await redis_pubsub.unsubscribe(channel_name)
