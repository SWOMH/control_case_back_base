from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, Text
from database.base import Base
from sqlalchemy.orm import Mapped, mapped_column
from database.types import intpk


class DocumentsUser(Base):
    __tablename__ = "documents_user"
    id: Mapped[intpk]
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("public.users.id"))
    document_id: Mapped[int] = mapped_column(Integer, ForeignKey("public.documents.id"))
    created_count: Mapped[int]
    created_limit: Mapped[int | None]
