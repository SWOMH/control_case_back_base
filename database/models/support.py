from database.types import intpk
from database.base import Base
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from sqlalchemy import (
    Integer, String, Boolean, DateTime, ForeignKey, Text, Enum, BigInteger
)
import enum


class SenderType(str, enum.Enum):
    USER = "user"
    CLIENT = "client"
    SUPPORT = "support"
    SYSTEM = "system"


class MessageStatus(str, enum.Enum):
    SENT = "sent"
    EDITED = "edited"
    DELETED = "deleted"


class ReasonCloseChat(Base):
    """Причина по которой оператор закрыл чат"""
    __tablename__ = "reason_close_chat"
    id: Mapped[intpk]
    reason: Mapped[str] = mapped_column(String(255), nullable=False)

class SupportHistoryDate(Base):
    """Даты захода в чат оператора и выхода из чата"""
    __tablename__ = "support_history_date"
    id: Mapped[intpk]
    date_join: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    date_leave: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

class Chat(Base):
    __tablename__ = "chat"
    id: Mapped[intpk]
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("public.users.id"), nullable=False)
    user_support_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("public.users.id", ondelete="SET NULL"), nullable=True
    )  # текущий оператор/юрист
    date_created: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    resolved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    date_close: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # связи
    messages = relationship("ChatMessage", back_populates="chat", cascade="all, delete-orphan")
    participants = relationship("ChatParticipant", back_populates="chat", cascade="all, delete-orphan")
    rating = relationship("ChatRating", back_populates="chat", uselist=False)


class ChatMessage(Base):
    __tablename__ = "chat"
    id: Mapped[intpk]
    chat_id: Mapped[int] = mapped_column(Integer, ForeignKey("chat.id", ondelete="CASCADE"), nullable=False)
    sender_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("public.users.id"), nullable=True)
    sender_type: Mapped[SenderType] = mapped_column(Enum(SenderType), nullable=False, default=SenderType.USER)
    message: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    status: Mapped[MessageStatus] = mapped_column(Enum(MessageStatus), nullable=False, default=MessageStatus.SENT)
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # связи
    chat = relationship("Chat", back_populates="messages")
    attachments = relationship("ChatAttachment", back_populates="message", cascade="all, delete-orphan")
    read_receipts = relationship("MessageReadReceipt", back_populates="message", cascade="all, delete-orphan")


class ChatAttachment(Base):
    __tablename__ = "chat_attachment"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    message_id: Mapped[int] = mapped_column(Integer, ForeignKey("chat_message.id", ondelete="CASCADE"), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)  # или хранить URL
    content_type: Mapped[str] = mapped_column(String(128), nullable=True)
    size: Mapped[int] = mapped_column(BigInteger, nullable=True)
    message = relationship("ChatMessage", back_populates="attachments")


class MessageReadReceipt(Base):
    __tablename__ = "message_read_receipt"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    message_id: Mapped[int] = mapped_column(Integer, ForeignKey("chat_message.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("public.users.id"), nullable=False)
    read_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    message = relationship("ChatMessage", back_populates="read_receipts")


class ChatParticipant(Base):
    __tablename__ = "chat_participant"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chat_id: Mapped[int] = mapped_column(Integer, ForeignKey("chat.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("public.users.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False)  # например: "client", "support", "lawyer"
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    left_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    chat = relationship("Chat", back_populates="participants")


class SupportHistoryDate(Base):
    __tablename__ = "support_history_date"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date_join: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    date_leave: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SupportHistoryChat(Base):
    __tablename__ = "support_history_chat"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chat_id: Mapped[int] = mapped_column(Integer, ForeignKey("chat.id"), nullable=False)
    old_support_id: Mapped[int] = mapped_column(Integer, ForeignKey("public.users.id"), nullable=False)
    reason_id: Mapped[int] = mapped_column(Integer, ForeignKey("reason_close_chat.id"), nullable=True)
    history_date_id: Mapped[int] = mapped_column(Integer, ForeignKey("support_history_date.id"), nullable=True)
    # можно добавить дополнительные поля: note, transferred_to, etc.


class ClientLawyerAssignment(Base):
    __tablename__ = "client_lawyer_assignment"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_id: Mapped[int] = mapped_column(Integer, ForeignKey("public.users.id"), nullable=False)
    lawyer_id: Mapped[int] = mapped_column(Integer, ForeignKey("public.users.id"), nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    unassigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # связь: можно добавить relationship к пользователям


class ChatRating(Base):
    __tablename__ = "chat_rating"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chat_id: Mapped[int] = mapped_column(Integer, ForeignKey("chat.id", ondelete="CASCADE"), nullable=False, unique=True)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)  # например 1-5
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    chat = relationship("Chat", back_populates="rating")

