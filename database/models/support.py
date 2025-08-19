from database.types import intpk
from database.base import Base
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from sqlalchemy import (
    Integer, String, Boolean, DateTime, ForeignKey, Text, Enum, BigInteger
)
import enum
from sqlalchemy import Index, desc


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
    """
    Причина по которой оператор закрыл чат

    Нужно фиксировать, почему чат завершили: «Проблема решена», «Клиент не ответил», «Передан другому юристу».

    Используется для аналитики и отчётов.

    Как будет использоваться:

        При закрытии чата оператор выбирает причину из списка.
        В support_history_chat сохраняется ссылка на причину.
    """
    __tablename__ = "reason_close_chat"
    __table_args__ = {'schema': 'public'}
    id: Mapped[intpk]
    reason: Mapped[str] = mapped_column(String(255), nullable=False)


class SupportHistoryDate(Base):
    """
    Даты захода в чат оператора и выхода из чата

    Чтобы видеть рабочую нагрузку и активность операторов.

    Можно анализировать, сколько времени оператор был в чате.

    Как будет использоваться:

        Запись создаётся при входе оператора и обновляется при выходе.
        Ссылается из support_history_chat.
    """
    __tablename__ = "support_history_date"
    __table_args__ = {'schema': 'public'}
    id: Mapped[intpk]
    date_join: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    date_leave: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Chat(Base):
    """
    Это «контейнер» для сообщений, участников, рейтинга.

    Как будет использоваться:

        Создаётся при первом сообщении пользователя.
        Через relationship можно быстро получить все сообщения, участников и рейтинг.
    """
    __tablename__ = "chat"
    __table_args__ = {'schema': 'public',
                      'extend_existing': True}
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
    """
    Хранит историю переписки.

    Поддерживает вложения и отметки о прочтении.

    Как будет использоваться:

        Добавляется каждое сообщение пользователя или оператора.
        При редактировании обновляется edited_at и status.
        Можно быстро сортировать по времени (есть индекс).
    """
    __tablename__ = "chat_messages"
    id: Mapped[intpk]
    chat_id: Mapped[int] = mapped_column(Integer, ForeignKey("public.chat.id", ondelete="CASCADE"), nullable=False)
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

    __table_args__ = (
        Index('ix_chat_messages_chat_id_created_at', 'chat_id', desc('created_at')),
    )


class ChatAttachment(Base):
    """
    Чтобы не хранить файл прямо в БД, а только ссылку.

    Как будет использоваться:

        Загружается вместе с сообщением.
        Через relationship легко получить вложения для сообщения.
    """
    __tablename__ = "chat_attachment"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    message_id: Mapped[int] = mapped_column(Integer, ForeignKey("chat_messages.id", ondelete="CASCADE"), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)  # или хранить URL
    content_type: Mapped[str] = mapped_column(String(128), nullable=True)
    size: Mapped[int] = mapped_column(BigInteger, nullable=True)
    message = relationship("ChatMessage", back_populates="attachments")


class MessageReadReceipt(Base):
    """
    Чтобы показывать пользователю статус «прочитано».
    Чтобы аналитика видела, читают ли операторы сообщения вовремя.

    Как будет использоваться:

        Создаётся при открытии чата пользователем или оператором.
    """
    __tablename__ = "message_read_receipt"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    message_id: Mapped[int] = mapped_column(Integer, ForeignKey("chat_messages.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("public.users.id"), nullable=False)
    read_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    message = relationship("ChatMessage", back_populates="read_receipts")


class ChatParticipant(Base):
    """
    Важна история участников, если чат переводится от одного юриста к другому.

    Как будет использоваться:

        Запись добавляется при входе пользователя или юриста в чат.
        Можно фильтровать чаты по роли участников.
    """
    __tablename__ = "chat_participant"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chat_id: Mapped[int] = mapped_column(Integer, ForeignKey("public.chat.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("public.users.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False)  # например: "client", "support", "lawyer"
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    left_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    chat = relationship("Chat", back_populates="participants")



class SupportHistoryChat(Base):
    """
    Чтобы видеть, кто раньше вел чат, и почему его сменили.

    Как будет использоваться:

        Создаётся при передаче чата другому юристу или закрытии.
    """
    __tablename__ = "support_history_chat"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chat_id: Mapped[int] = mapped_column(Integer, ForeignKey("public.chat.id"), nullable=False)
    old_support_id: Mapped[int] = mapped_column(Integer, ForeignKey("public.users.id"), nullable=False)
    reason_id: Mapped[int] = mapped_column(Integer, ForeignKey("public.reason_close_chat.id"), nullable=True)
    history_date_id: Mapped[int] = mapped_column(Integer, ForeignKey("public.support_history_date.id"), nullable=True)
    # можно добавить дополнительные поля: note, transferred_to, etc.


class ClientLawyerAssignment(Base):
    """
    Для закрепления клиента за конкретным юристом.

    Как будет использоваться:

        При создании чата можно выбрать закреплённого юриста.
        Можно строить аналитику: сколько клиентов у юриста.
    """
    __tablename__ = "client_lawyer_assignment"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_id: Mapped[int] = mapped_column(Integer, ForeignKey("public.users.id"), nullable=False)
    lawyer_id: Mapped[int] = mapped_column(Integer, ForeignKey("public.users.id"), nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    unassigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # связь: можно добавить relationship к пользователям


class ChatRating(Base):
    """
    Чтобы собирать обратную связь о работе оператора/юриста.

    Как будет использоваться:

        Создаётся после завершения чата, один раз на чат.
        Через relationship можно сразу получить рейтинг из чата.
    """
    __tablename__ = "chat_rating"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chat_id: Mapped[int] = mapped_column(Integer, ForeignKey("public.chat.id", ondelete="CASCADE"), nullable=False, unique=True)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)  # например 1-5
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    chat = relationship("Chat", back_populates="rating")

