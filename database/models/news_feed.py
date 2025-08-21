from database.base import Base
from decimal import Decimal
from datetime import datetime
from sqlalchemy import Date, DateTime, ForeignKey, Numeric, Text, text
from sqlalchemy.orm import Mapped, mapped_column
from database.types import intpk, u_id


class Posts(Base):
    __tablename__ = "posts"
    id: Mapped[intpk]
    time_created: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    title: Mapped[str]
    img: Mapped[str | None]
    video: Mapped[str | None]
    moderation: Mapped[bool]
    author: Mapped[u_id]


class Likes(Base):
    __tablename__ = 'likes'
    id: Mapped[intpk]
    user_id: Mapped[u_id]
    post_id: Mapped[int] = mapped_column(ForeignKey('public.posts.id'))


class Comments(Base):
    __tablename__ = "comments_posts"
    id: Mapped[intpk]
    user_id: Mapped[int] = mapped_column(ForeignKey('public.users.id', ondelete='CASCADE'), nullable=False)
    post_id: Mapped[int] = mapped_column(ForeignKey('public.posts.id', ondelete='CASCADE'), nullable=False)
    text: Mapped[str | None]
    image: Mapped[str | None]
    deleted: Mapped[bool] = mapped_column(default=False)


class CommentAnswer(Base):
    __tablename__ = "comments_answer"
    id: Mapped[intpk]


