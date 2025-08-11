from sqlalchemy import ForeignKey
from database.types import intpk
from database.base import Base
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime


class CourtUser(Base):
    __tablename__ = "court"
    id: Mapped[intpk]
    user_id: Mapped[int] = mapped_column(ForeignKey('public.users.id', ondelete='CASCADE'), nullable=False)
    href_case: Mapped[str]

class Stage(Base):
    __tablename__ = "court"
    id: Mapped[intpk]
    court_id: Mapped[int] = mapped_column(ForeignKey('public.court.id', ondelete='CASCADE'), nullable=False)
    stage_name: Mapped[str]
    description: Mapped[str | None]
    date_stage: Mapped[datetime]
    appointed: Mapped[str | None]
    automatically: Mapped[bool]
    appointed_employee: Mapped[str]
    appointed_employee_id: Mapped[int]
    

