from sqlalchemy import ForeignKey
from database.types import intpk
from database.base import Base
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime


class Stage(Base):
    __tablename__ = "court_stage"
    id: Mapped[intpk]
    user_id: Mapped[int] = mapped_column(ForeignKey('public.users.id'), nullable=False)
    stage_name: Mapped[str]
    description: Mapped[str | None]
    date_stage: Mapped[datetime]
    appointed: Mapped[str | None]
    automatically: Mapped[bool]
    appointed_employee: Mapped[str]
    appointed_employee_id: Mapped[int | None] = mapped_column(ForeignKey('public.users.id'), nullable=True)
    

