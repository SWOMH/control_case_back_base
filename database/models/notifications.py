from decimal import Decimal
from datetime import date
from sqlalchemy import Date, DateTime, ForeignKey, Numeric, Text, text
from database.base import Base
from sqlalchemy.orm import Mapped, mapped_column
from database.types import intpk
from typing import Optional


class Notifications(Base):
    __tablename__ = "notifications"
    id: Mapped[intpk]
    user: Mapped[int] = mapped_column()
    title: Mapped[str]
    description: Mapped[str]
    link: Mapped[Optional[str]]
