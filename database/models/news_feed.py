from database.base import Base
from decimal import Decimal
from datetime import date
from sqlalchemy import Date, DateTime, ForeignKey, Numeric, Text, text
from sqlalchemy.orm import Mapped, mapped_column
from database.types import intpk


class Posts(Base):
    __tablename__ = "posts"
    id: Mapped[intpk]
    title: Mapped[str]
    img: Mapped[str | None]
    video: Mapped[str | None]


class Comments(Base):
    __tablename__ = "comments_posts"
    id: Mapped[intpk]
    user_id: Mapped[int] = mapped_column(ForeignKey('public.users.id', ondelete='CASCADE'), nullable=False)
    post_id: Mapped[int] = mapped_column(ForeignKey('public.posts.id', ondelete='CASCADE'), nullable=False)
    text: Mapped[str | None]
    image: Mapped[str | None]

class CommentAnswer(Base):
    __tablename__ = "comments_answer"
    id: Mapped[intpk]


