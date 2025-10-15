from typing import Optional

from database.base import Base
from decimal import Decimal
from datetime import datetime
from sqlalchemy import Date, DateTime, ForeignKey, Numeric, Text, text, func, String, Boolean, Integer, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, backref, mapped_column, relationship
from database.types import intpk, u_id
from enum import Enum
from sqlalchemy.dialects.postgresql import ENUM as PgEnum

class MediaType(str, Enum):
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    DOCUMENT = "document"
    OTHER = "other"
    

# TODO: Нужно будет заготовить файлы под S3
class Post(Base):
    __tablename__ = "posts"
    __table_args__ = {'schema': 'public'}

    id: Mapped[intpk]
    time_created: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    time_updated: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, onupdate=func.now()
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # основное тело поста 

    moderated: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    published: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    time_published: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    author_id: Mapped[u_id] = mapped_column(Integer, ForeignKey("public.users.id", ondelete="SET NULL"), nullable=True)

    # связи
    # author = relationship("Users", backref="posts")  # если модель Users в проекте называется Users
    comments = relationship("Comment", back_populates="post", cascade="all, delete-orphan")
    likes = relationship("Like", back_populates="post", cascade="all, delete-orphan")
    media = relationship("Media", back_populates="post", cascade="all, delete-orphan")
    # индексы
    __table_args__ = (
        Index("ix_posts_time_created", "time_created"),
        {'schema': 'public'}
    )

class Media(Base):
    __tablename__ = "media"
    __table_args__ = {'schema': 'public'}
    id: Mapped[intpk]
    url: Mapped[str] = mapped_column(String, nullable=False)
    deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    type: Mapped[MediaType] = mapped_column(PgEnum(MediaType, name='media_type_enum', create_constraint=True, create_type=False), nullable=False)
    post_id: Mapped[int] = mapped_column(Integer, ForeignKey("public.posts.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    post = relationship("Post", back_populates="media")

class Like(Base):
    __tablename__ = "likes"
    __table_args__ = (
        UniqueConstraint("user_id", "post_id", name="uq_likes_user_post"),
        {'schema': 'public'}
    )

    id: Mapped[intpk]
    user_id: Mapped[u_id]
    post_id: Mapped[int] = mapped_column(Integer, ForeignKey("public.posts.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # user = relationship("Users", backref="likes")
    post = relationship("Post", back_populates="likes")


class Comment(Base):
    __tablename__ = "comments_posts"
    __table_args__ = {'schema': 'public'}

    id: Mapped[intpk]
    user_id: Mapped[u_id]
    post_id: Mapped[int] = mapped_column(Integer, ForeignKey("public.posts.id", ondelete="CASCADE"), nullable=False)

    text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    image_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)

    parent_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("public.comments_posts.id", ondelete="CASCADE"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    edited_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, onupdate=func.now())
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)  # soft-delete
    user_reply_id: Mapped[Optional[u_id]] = mapped_column(Integer, ForeignKey("public.users.id", ondelete="SET NULL"), nullable=True)
    # user = relationship("Users", backref="comments")
    post = relationship("Post", back_populates="comments")
    # parent = relationship(
    #     "Comment",
    #     remote_side=[id],
    #     backref=backref("replies", cascade="all, delete-orphan")
    # )


