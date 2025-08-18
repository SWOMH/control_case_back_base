from decimal import Decimal
from datetime import date
from sqlalchemy import Date, DateTime, ForeignKey, Numeric, Text, text
from database.base import Base
from sqlalchemy.orm import Mapped, mapped_column
from database.types import intpk


class Notifications(Base):
    __tablename__ = "notifications"
    id: Mapped[intpk]
    user: Mapped[int] = mapped_column()
