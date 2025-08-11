from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, Text
from database.base import Base
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database.types import intpk

class Documents(Base):
    __tablename__ = "documents"
    id: Mapped[intpk]
    document_name: Mapped[str]
    document_description: Mapped[str | None]
    path: Mapped[str]
    instruction: Mapped[str] # инструкция для клиента
    price: Mapped[Decimal] = mapped_column(Numeric(10,2), default=0)
    sale: Mapped[bool]
    
    field = relationship("DocumentFields", back_populates="documents")
    tags = relationship("DocumentTags", back_populates="documents")

class DocumentFields(Base):
    __tablename__ = "document_fields"
    id: Mapped[intpk]
    document_id: Mapped[int] = mapped_column(ForeignKey("public.documents.id"))
    field_name: Mapped[str]
    field_description: Mapped[str | None]
    service_field: Mapped[str] # поле в самом документе для замены
    documents = relationship("Documents", back_populates="field")

class DocumentTags(Base):
    """Тэги для краткой сути документа или для легкого поиска, пока не решил"""
    __tablename__ = "document_tags"
    id: Mapped[intpk]
    tag_name: Mapped[str]
    document_id: Mapped[int] = mapped_column(ForeignKey("public.documents.id"))
    documents = relationship("Documents", back_populates="field")