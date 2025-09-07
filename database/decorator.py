from functools import wraps
from typing import Callable, Coroutine, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text


def connection(self, isolation_level: Optional[str] = None, commit: bool = True):
    """
    Декоратор для управления сессией с возможностью настройки уровня изоляции и коммита.
    Теперь можно выбирать подходящий уровень изоляции для разных операций:

    READ COMMITTED — для обычных запросов (по умолчанию в PostgreSQL).
    SERIALIZABLE — для финансовых операций, требующих максимальной надежности.
    REPEATABLE READ — для отчетов и аналитики.

    Параметры:
    - `isolation_level`: уровень изоляции для транзакции (например, "SERIALIZABLE").
    - `commit`: если `True`, выполняется коммит после вызова метода.

    # Чтение данных (на самом деле нах не надо, ибо по умолчанию так и проходит)
    @connection(isolation_level="READ COMMITTED")
    async def get_user(self, session, user_id: int):
        ...

    # Финансовая операция
    @connection(isolation_level="SERIALIZABLE", commit=False)
    async def transfer_money(self, session, from_id: int, to_id: int):
        ...
    """
    def decorator(method):
        @wraps(method)
        async def wrapper(*args, **kwargs):
            async with self.session_maker() as session:
                try:
                    if isolation_level:
                        await session.execute(text(f"SET TRANSACTION ISOLATION LEVEL {isolation_level}"))
                    result = await method(*args, session=session, **kwargs)
                    if commit:
                        await session.commit()
                    return result
                except Exception as e:
                    await session.rollback()
                    raise e
                finally:
                    await session.close()
        return wrapper
    return decorator