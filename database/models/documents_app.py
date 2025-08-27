from decimal import Decimal
from datetime import date
from sqlalchemy import Date, DateTime, ForeignKey, Numeric, Text, text
from database.base import Base
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database.types import intpk


class DocumentsApp(Base):
    __tablename__ = "documents"
    id: Mapped[intpk]
    document_name: Mapped[str]
    document_description: Mapped[str | None]
    path: Mapped[str]
    instruction: Mapped[str | None]  # инструкция для клиента
    price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    sale: Mapped[bool]
    limit_free: Mapped[int | None]
    activity: Mapped[bool] = mapped_column(nullable=False, default=True)

    field = relationship("DocumentFields", back_populates="documents")
    # tags = relationship("DocumentTags", back_populates="documents")


class DocumentFields(Base):
    __tablename__ = "document_fields"
    id: Mapped[intpk]
    document_id: Mapped[int] = mapped_column(ForeignKey("public.documents.id", ondelete='CASCADE'), nullable=False)
    field_name: Mapped[str]
    field_description: Mapped[str | None]
    field_example: Mapped[str | None]
    service_field: Mapped[str]  # поле в самом документе для замены
    documents = relationship("DocumentsApp", back_populates="field")

# TODO: переделать на ассоциативные таблицы (решил вообще убрать. Добавлю по необходимости в проде)
# class DocumentTags(Base):
#     """Тэги для краткой сути документа или для легкого поиска, пока не решил"""
#     __tablename__ = "document_tags"
#     id: Mapped[intpk]
#     tag_name: Mapped[str]
#     document_id: Mapped[int] = mapped_column(ForeignKey("public.documents.id", ondelete='CASCADE'), nullable=False)
#     documents = relationship("DocumentsApp", back_populates="field")


class PurchasedDocuments(Base):
    __tablename__ = "purchased_documents"
    id: Mapped[intpk]
    document_id: Mapped[int] = mapped_column(ForeignKey("public.documents.id", ondelete='CASCADE'), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey('public.users.id', ondelete='CASCADE'), nullable=False)
    amount_sum: Mapped[int | None]  # за какую сумму куплен документ


class DocumentCreated(Base):
    __tablename__ = "document_created"
    id: Mapped[intpk]
    document_id: Mapped[int] = mapped_column(ForeignKey("public.documents.id", ondelete='CASCADE'), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey('public.users.id', ondelete='CASCADE'), nullable=False)
    created: Mapped[bool]
    date: Mapped[date | None] = mapped_column(Date, server_default=text("CURRENT_DATE"), nullable=True)
