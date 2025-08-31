from datetime import datetime
from decimal import Decimal
import enum
from sqlalchemy import (
    Integer, String, DateTime, Numeric, ForeignKey, Text, Enum, JSON, Index, Date
)
from database.base import Base
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database.types import intpk
from datetime import date


class AgreementClient(Base):
    """Договор клиента"""
    __tablename__ = 'agreements_clients'
    id: Mapped[intpk]
    user_id: Mapped[int] = mapped_column(ForeignKey('public.users.id'))
    date_conclusion: Mapped[date] = mapped_column(Date)
    price: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    discount_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    price_after_discount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)

    __table_args__ = (
        Index('ix_agreements_clients_user_id', 'user_id'),  # Для поиска договоров по пользователю
        Index('ix_agreements_clients_date_conclusion', 'date_conclusion'),  # Для фильтрации по дате
    )


class Discount(Base):
    """Таблица скидок"""
    __tablename__ = 'discount'
    id: Mapped[intpk]
    discount_type: Mapped[str] = mapped_column(nullable=False)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    date_create: Mapped[date] = mapped_column(Date, nullable=False)

    __table_args__ = (
        Index('ix_discount_date_create', 'date_create'),  # Для фильтрации по дате создания
        Index('ix_discount_type', 'discount_type'),  # Для поиска по типу скидки
    )


class DiscountAssociation(Base):
    """Ассоциативная таблица для скидок"""
    __tablename__ = 'discount_association'
    id: Mapped[intpk]
    agreement_id: Mapped[int] = mapped_column(ForeignKey('public.agreements_clients.id'), nullable=False)
    discount_id: Mapped[int] = mapped_column(ForeignKey('public.discount.id'), nullable=False)
    active: Mapped[bool] = mapped_column(server_default=Text('true'), nullable=False)

    __table_args__ = (
        Index('ix_discount_association_agreement_id', 'agreement_id'),  # Для поиска скидок по договору
        Index('ix_discount_association_discount_id', 'discount_id'),  # Для поиска договоров по скидке
        Index('ix_discount_association_active', 'active'),  # Для фильтрации по активности
        Index('ix_discount_association_agreement_discount', 'agreement_id', 'discount_id'),
    # Составной индекс для частых JOIN
    )


