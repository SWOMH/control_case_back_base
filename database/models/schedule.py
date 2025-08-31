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


class StatusPayment(str, Enum):
    PAID = 'paid'  # оплачено
    OVERDUE = 'overdue'  # просрочено
    EXPECTED = 'expected'  # ожидается
    DEDUCTED = 'deducted'  # вычтено


class PaymentSchedule(Base):
    __tablename__ = 'payment_schedule'
    id: [intpk]
    agreement_id: Mapped[int] = mapped_column(ForeignKey('public.agreements_clients.id'), nullable=False)
    status: Mapped[StatusPayment] = mapped_column(Enum(StatusPayment), nullable=False, default=StatusPayment.EXPECTED)
    deducted_id: Mapped[int | None] = mapped_column(ForeignKey('public.discount.id'), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)

    __table_args__ = (
        Index('ix_payment_schedule_agreement_id', 'agreement_id'),  # Для поиска платежей по договору
        Index('ix_payment_schedule_status', 'status'),  # Для фильтрации по статусу
        Index('ix_payment_schedule_date', 'date'),  # Для фильтрации по дате
        Index('ix_payment_schedule_agreement_status', 'agreement_id', 'status'),  # Составной индекс
        Index('ix_payment_schedule_deducted_id', 'deducted_id'),  # Для поиска по вычету
    )


# ТУт нужно таблицу с историей ебануть еще
class HistoryEditSchedule(Base):
    """Тут будет история изменений расписания платежей"""
    __tablename__ = 'history_edit_schedule'
    id: Mapped[intpk]
    schedule_id: Mapped[int] = mapped_column(ForeignKey('public.payment_schedule.id'), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[StatusPayment] = mapped_column(Enum(StatusPayment), nullable=False, default=StatusPayment.EXPECTED)

    __table_args__ = (
        Index('ix_history_edit_schedule_schedule_id', 'schedule_id'),  # Для поиска истории по платежу
        Index('ix_history_edit_schedule_date', 'date'),  # Для фильтрации по дате изменения
        Index('ix_history_edit_schedule_status', 'status'),  # Для фильтрации по статусу
    )
