from database.types import intpk
from database.base import Base
from sqlalchemy import Integer, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime


class ReasonCloseChat(Base):
    """Причина по которой оператор закрыл чат"""
    __tablename__ = "reason_close_chat"
    id: Mapped[intpk]
    reason: Mapped[str]

class SupportHistoryDate(Base):
    """Даты захода в чат оператора и выхода из чата"""
    __tablename__ = "support_history_date"
    id: Mapped[intpk]
    date_join: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    date_leave: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

class SupportHistoryChat(Base):
    """История диалога поддержки, в случае закрытия чата оператором"""
    __tablename__ = "support_history_chat"
    id: Mapped[intpk]
    chat_id: Mapped[int] = mapped_column(Integer, ForeignKey("public.chat.id"))
    old_support_id: Mapped[int] = mapped_column(Integer, ForeignKey("public.user.id"))
    reason: Mapped[int] = mapped_column(Integer, ForeignKey("public.reason_close_chat.id"))
    history_date: Mapped[int] = mapped_column(Integer, ForeignKey("public.")) # Указывает на даты открытия и закрытия


class Chat(Base):
    __tablename__ = "chat"
    id: Mapped[intpk]
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("public.user.id"))
    user_support_id: Mapped[int] = mapped_column(Integer, ForeignKey("public.user.id"))
    date_created: Mapped[datetime]
    active: Mapped[bool] = mapped_column(nullable=False, default=True)  # Активен ли еще
    resolved: Mapped[bool] = mapped_column(nullable=False, default=False)  # Решен
    date_close: Mapped[datetime | None]


class ChatMessage(Base):
    __tablename__ = "chat"
    id: Mapped[intpk]
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("public.user.id"))
    message: Mapped[str]
    time: Mapped[datetime]
    