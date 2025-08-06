from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, Text
from database.base import Base
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database.types import intpk



class HistoryBalanceDeductions(Base):
    __tablename__ = "history_deductions"
    id: Mapped[intpk]
    period: Mapped[datetime] = mapped_column(DateTime, nullable=False) 
    value: Mapped[Decimal] = mapped_column(Numeric(10,2), default=0)    
    user_id: Mapped[int] = mapped_column(ForeignKey('public.users.id', ondelete='CASCADE'), nullable=False)
    user = relationship("Users", back_populates="history_balance")

class HistoryBalance(Base): # пополнение
    __tablename__ = "history_bonuses"
    id: Mapped[intpk]
    period: Mapped[datetime] = mapped_column(DateTime, nullable=False) 
    value: Mapped[Decimal] = mapped_column(Numeric(10,2), default=0)    
    user_id: Mapped[int] = mapped_column(ForeignKey('public.users.id', ondelete='CASCADE'), nullable=False)
    user = relationship("Users", back_populates="history_balance")
