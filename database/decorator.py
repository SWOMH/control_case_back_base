from functools import wraps
from typing import Callable, Coroutine, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text


def connection(isolation_level: Optional[str] = None, commit: bool = True):
    def decorator(method: Coroutine):
        @wraps(method)
        async def wrapper(self, *args, **kwargs):
            async with self.Session() as session:
                try:
                    if isolation_level:
                        await session.execute(text(f"SET TRANSACTION ISOLATION LEVEL {isolation_level}"))
                    result = await method(self, session=session, *args, **kwargs)
                    if commit:
                        await session.commit()
                    return result
                except Exception:
                    await session.rollback()
                    raise
        return wrapper
    return decorator