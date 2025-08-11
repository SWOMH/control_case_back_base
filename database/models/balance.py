from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, Text
from database.base import Base
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database.types import intpk

class TypeDeduction(Base):
    __tablename__ = "type_deduction"
    id: Mapped[intpk]
    type_name: Mapped[str]

class TypeReplenishment(Base):
    __tablename__ = "type_replenishment"
    id: Mapped[intpk]
    type_name: Mapped[str]
    

class HistoryBalanceDeductions(Base):
    __tablename__ = "history_deductions"
    id: Mapped[intpk]
    period: Mapped[datetime] = mapped_column(DateTime, nullable=False) 
    value: Mapped[Decimal] = mapped_column(Numeric(10,2), default=0)
    user_id: Mapped[int] = mapped_column(ForeignKey('public.users.id', ondelete='CASCADE'), nullable=False)
    type: Mapped[int] = mapped_column(ForeignKey('public.type_deduction.id'))


    user = relationship("Users", back_populates="history_balance")


class HistoryBalanceReplenishment(Base): # пополнение
    __tablename__ = "history_replenishment"
    id: Mapped[intpk]
    period: Mapped[datetime] = mapped_column(DateTime, nullable=False) 
    value: Mapped[Decimal] = mapped_column(Numeric(10,2), default=0)
    user_id: Mapped[int] = mapped_column(ForeignKey('public.users.id', ondelete='CASCADE'), nullable=False)
    type: Mapped[int] = mapped_column(ForeignKey('public.type_replenishment.id'))


    user = relationship("Users", back_populates="history_balance")
