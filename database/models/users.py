from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, Text, JSON
from database.base import Base
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database.types import intpk


class Users(Base):
    """Класс пользователя (пока хз как разделить права. 
    Добавить в юзера или сделать прям норм разделение прав)"""
    __tablename__ = "users"
    id: Mapped[intpk]
    login: Mapped[str]
    password: Mapped[str]    
    surname: Mapped[str] # фамилия
    first_name: Mapped[str] # имя
    patronymic: Mapped[str] # отчество
    balance: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)  # остаток на балансе 
    last_activity: Mapped[datetime]
    
    history_balance = relationship("HistoryBalance", back_populates='user')
    activity = relationship("Activity", back_populates="user")

class Activity(Base):
    __tablename__ = "users_activity"
    id: Mapped[intpk]
    user_id: Mapped[int] = mapped_column(ForeignKey('public.users.id', ondelete='CASCADE'), nullable=False)
    user = relationship("Users", back_populates="activity")
    page: Mapped[JSON]
    


