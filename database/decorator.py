from functools import wraps
from typing import Callable, Coroutine, Any
from sqlalchemy.ext.asyncio import AsyncSession


def connection(method: Callable[..., Coroutine[Any, Any, Any]]):
    @wraps(method)
    async def wrapper(self, *args, **kwargs):
        async with self.Session() as session:
            try:
                result = await method(self, session=session, *args, **kwargs)
                await session.commit()
                return result
            except Exception as e:
                await session.rollback()
                raise e
    return wrapper