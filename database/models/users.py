from datetime import datetime
from decimal import Decimal
from typing import Optional
from sqlalchemy import Index

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
    email: Mapped[Optional[str]] = mapped_column(String(254), nullable=True, unique=True)
    password: Mapped[str]    
    surname: Mapped[str]  # фамилия
    first_name: Mapped[str]  # имя
    patronymic: Mapped[str]  # отчество
    is_client: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)  # флаг клиента
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_staff: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)  # доступ к админке
    is_support: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_banned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_lawyer: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_activity: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    locale: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    timezone: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    preferences: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # history_balance = relationship("HistoryBalance", back_populates='user')
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

# -----------------------
# Activity / Audit
# -----------------------
class Activity(Base):
    __tablename__ = "user_activity"
    id: Mapped[intpk] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("public.users.id", ondelete="CASCADE"), nullable=False)
    path: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)   # страница или endpoint
    ip_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    extra: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    user = relationship("Users", back_populates="activity")
    


