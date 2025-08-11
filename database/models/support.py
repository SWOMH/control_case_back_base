from database.types import intpk
from database.base import Base
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime


class Chat(Base):
    __tablename__ = "chat"
    id: Mapped[intpk]
    user_id: Mapped[int]
    user_support_id: Mapped[int]
    date_created: Mapped[datetime]
    active: Mapped[bool] = mapped_column(nullable=False, default=True) # Активен ли еще
    resolved: Mapped[bool] = mapped_column(nullable=False, default=False)# Решен
    date_close: Mapped[datetime | None]


class ChatMessage(Base):
    __tablename__ = "chat"
    id: Mapped[intpk]
    user_id: Mapped[int]
    message: Mapped[str]
    time: Mapped[datetime]
    