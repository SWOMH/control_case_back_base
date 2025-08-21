from typing import Optional

from database.base import Base
from decimal import Decimal
from datetime import datetime
from sqlalchemy import Date, DateTime, ForeignKey, Numeric, Text, text, func, String, Boolean, Integer, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database.types import intpk, u_id

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
    image_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    video_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)

    moderated: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    published: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    author_id: Mapped[u_id] = mapped_column(Integer, ForeignKey("public.users.id", ondelete="SET NULL"), nullable=True)

    # связи
    author = relationship("Users", backref="posts")  # если модель Users в проекте называется Users
    comments = relationship("Comment", back_populates="post", cascade="all, delete-orphan")
    likes = relationship("Like", back_populates="post", cascade="all, delete-orphan")

    # индексы
    __table_args__ = (
        Index("ix_posts_time_created", "time_created"),
        {'schema': 'public'}
    )


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

    user = relationship("Users", backref="likes")
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

    user = relationship("Users", backref="comments")
    post = relationship("Post", back_populates="comments")
    replies = relationship("Comment", backref=relationship("parent", remote_side=[id]), cascade="all, delete-orphan")


