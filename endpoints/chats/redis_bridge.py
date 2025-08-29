import asyncio
import json
import redis.asyncio as redis
from typing import Callable, Awaitable


class RedisPubSub:
    """
    Простая обёртка над redis.asyncio PubSub.
    Подписываемся на каналы динамически.
    Запускает слушающий таск, который вызывает callback(channel, message_dict).
    """
    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self.redis = redis.from_url(redis_url, decode_responses=True)
        self.pubsub = self.redis.pubsub(ignore_subscribe_messages=True)
        self._task = None
        self._callback: Callable[[str, dict], Awaitable[None]] | None = None
        self._running = False

    async def start(self, message_callback: Callable[[str, dict], Awaitable[None]]):
        """
        Запускаем слушатель. Должно быть вызвано один раз при старте приложения.
        """
        if self._running:
            return
        self._callback = message_callback
        self._running = True
        self._task = asyncio.create_task(self._reader_loop())

    async def subscribe(self, channel: str):
        await self.pubsub.subscribe(channel)

    async def unsubscribe(self, channel: str):
        await self.pubsub.unsubscribe(channel)

    async def publish(self, channel: str, message: dict):
        await self.redis.publish(channel, json.dumps(message, default=str))

    async def _reader_loop(self):
        try:
            while self._running:
                msg = await self.pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if msg is None:
                    await asyncio.sleep(0.01)
                    continue
                # msg example: {'type': 'message', 'pattern': None, 'channel': 'chats:123', 'data': '{"type":"message",...}'}
                channel = msg.get("channel")
                data = msg.get("data")
                try:
                    payload = json.loads(data)
                except Exception:
                    payload = {"raw": data}
                if self._callback:
                    # callback должен быть async
                    await self._callback(channel, payload)
        except asyncio.CancelledError:
            pass
        finally:
            await self.pubsub.close()

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
            await self.pubsub.close()
            await self.redis.close()
