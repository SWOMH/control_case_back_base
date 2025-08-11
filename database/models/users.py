from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, Text, JSON, Column, Integer, Boolean, String, Table
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
    client: Mapped[bool]
    balance: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)  # остаток на балансе 
    last_activity: Mapped[datetime]    
    
    history_balance = relationship("HistoryBalance", back_populates='user')
    activity = relationship("Activity", back_populates="user")
    groups = relationship("Group", secondary="user_group_association", back_populates="users")


class Group(Base):
    __tablename__ = 'groups'
    id: Mapped[intpk]
    name: Mapped[str] = mapped_column(nullable=False)
    
    users = relationship("Users", secondary="user_group_association", back_populates="groups")


class Token(Base):
    __tablename__ = 'tokens'
    id: Mapped[intpk]
    user_id: Mapped[int] = mapped_column(ForeignKey('public.users.id', ondelete='CASCADE'), nullable=False)
    token: Mapped[str] = mapped_column(nullable=False)
    refresh_token: Mapped[str | None] = mapped_column(nullable=True)
    user = relationship("Users", back_populates="tokens")

user_group_association = Table(
    'user_group_association',
    Base.metadata,
    Column('user_id', Integer, ForeignKey('public.users.id', ondelete='CASCADE')),
    Column('group_id', Integer, ForeignKey('public.groups.id', ondelete='CASCADE')),
    Column('active', Boolean, default=True)
)

group_permission_association = Table(
    'group_permission_association',
    Base.metadata,
    Column('group_id', Integer, ForeignKey('public.groups.id', ondelete='CASCADE')),
    Column('permission', String, nullable=False)
)

class Activity(Base):
    __tablename__ = "users_activity"
    id: Mapped[intpk]
    user_id: Mapped[int] = mapped_column(ForeignKey('public.users.id', ondelete='CASCADE'), nullable=False)
    user = relationship("Users", back_populates="activity")
    page: Mapped[JSON]
    


