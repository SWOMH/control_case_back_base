from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from datetime import datetime
from typing import Optional, List
from database.decorator import connection
from database.main_connection import DataBaseMainConnect
from database.models.balance import UserBalance
from exceptions.database_exc.balance_exceptions import BalanceUserNotFoundException
from schemas.balance_schema import UserBalanceResponse


class BalanceMain(DataBaseMainConnect):

    @connection()
    async def get_balance_by_id(self, user_id: int, session: AsyncSession) -> UserBalance:
        """Получение баланса по id пользователя"""
        balance = await session.execute(select(UserBalance).where(UserBalance.user_id == user_id))
        balance_data = balance.scalar_one_or_none()
        if balance_data is None:
            raise BalanceUserNotFoundException
        return balance_data

    # @connection(isolation_level='SERIALIZABLE')
    # async def replenishment_acquiring(self, ):