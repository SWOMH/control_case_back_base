from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, Text
from database.base import Base
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database.types import intpk

class TypeOperation(Base):
    __tablename__ = "type_operation"
    id: Mapped[intpk]
    type_name: Mapped[str]


class HistoryBalanceOperations(Base):  # пополнение
    __tablename__ = "history_balance_operations"
    id: Mapped[intpk]
    period: Mapped[datetime] = mapped_column(DateTime, nullable=False) 
    value: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    user_id: Mapped[int] = mapped_column(ForeignKey('public.users.id', ondelete='CASCADE'), nullable=False)
    type: Mapped[int] = mapped_column(ForeignKey('public.type_replenishment.id'))


    user = relationship("Users", back_populates="history_balance")
