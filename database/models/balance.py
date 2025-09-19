from datetime import datetime
from decimal import Decimal
import enum
from sqlalchemy import (
    Integer, String, DateTime, Numeric, ForeignKey, Text, JSON, Index, event
)
import uuid
from database.base import Base
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database.types import intpk
from sqlalchemy.dialects.postgresql import ENUM as PgEnum


# === Enums ===
class TransactionStatus(str, enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"


class TransactionDirection(str, enum.Enum):
    CREDIT = "credit"  # пополнение, + к балансу
    DEBIT = "debit"    # списание, - от баланса


# === Тип операции (справочник) ===
class OperationType(Base):
    """справочник типов операций (используется для аналитики и понимания, почему изменился баланс)."""
    __tablename__ = "operation_type"
    id: Mapped[intpk] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)  # например: 'manual_topup', 'invoice_payment'
    title: Mapped[str] = mapped_column(String(255), nullable=False)             # человеко-читаемое имя
    direction: Mapped[TransactionDirection] = mapped_column(
        PgEnum(TransactionDirection, name='transaction_direction_enum', create_constraint=True, create_type=False), nullable=False, default=TransactionDirection.CREDIT
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


# === Текущий баланс пользователя (быстрая выборка) ===
class UserBalance(Base):
    """это таблица, где хранится актуальный баланс (быстрая выборка при оплате).
    Изменяем её атомарно (в транзакции) при каждой успешной операции."""
    __tablename__ = "user_balance"
    id: Mapped[intpk] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("public.users.id", ondelete="CASCADE"), nullable=False,
                                         unique=True)
    # Основной баланс (можно добавить reserved_balance для холда/резерва)
    balance: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0.00"))
    reserved_balance: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0.00"))  # Зарезервированные средства
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="RUB")  # ISO-4217
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    # связь к юзеру (если нужна)
    # user = relationship("User", back_populates="balance")  # при наличии модели User


# === Журнал операций (ledger) ===
class BalanceOperation(Base):
    """это журнал (ledger) всех операций: пополнений, списаний, возвратов.
    Всегда записываем операцию (immutable запись), указываем направление (credit/debit) и snapshot"""
    __tablename__ = "balance_operation"
    id: Mapped[intpk] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("public.users.id", ondelete="CASCADE"), nullable=False)
    operation_type_id: Mapped[int] = mapped_column(Integer, ForeignKey("public.operation_type.id"), nullable=False)
    direction: Mapped[TransactionDirection] = mapped_column(PgEnum(TransactionDirection, name='transaction_direction_enum', create_constraint=True, create_type=False), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2),
                                            nullable=False)  # положительное число; sign определяется direction
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="RUB")  # валюта. По сути не нужна, но пускай будет
    balance_after: Mapped[Decimal | None] = mapped_column(Numeric(18, 2),
                                                          nullable=True)  # snapshot баланса после операции
    status: Mapped[TransactionStatus] = mapped_column(PgEnum(TransactionStatus, name='transaction_status_enum', create_constraint=True, create_type=False), nullable=False,
                                                      default=TransactionStatus.COMPLETED)  # важен для обработки асинхронных платежей:
                                                                                            # сначала pending, потом completed/failed.
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    # внешние ссылки / идемпотентность
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)  # id от платежного шлюза / invoice
    reference_type: Mapped[str | None] = mapped_column(String(64), nullable=True)  # например 'invoice', 'subscription'
    reference_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # JSON — полезно хранить необязательные данные от платежного шлюза (raw payload).

    operation_type = relationship("OperationType")
    # user = relationship("User", back_populates="balance_operations")
    payment_request = relationship("PaymentRequest", back_populates="operation")


# === Индексы ===
Index("ix_balance_operation_user_id_created_at", BalanceOperation.user_id, BalanceOperation.created_at)
Index("ix_balance_operation_external_id", BalanceOperation.external_id)
Index("ix_user_balance_user_id", UserBalance.user_id, unique=True)


# === Запрос на оплату ===
class PaymentRequest(Base):
    __tablename__ = "payments_requests"

    id: Mapped[intpk] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("public.users.id", ondelete="CASCADE"), nullable=False)

    # orderId будет уникальным бизнес-ключом (для банка)
    orderId: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)

    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    status: Mapped[TransactionStatus] = mapped_column(
        PgEnum(TransactionStatus, name='transaction_status_enum', create_constraint=True, create_type=False), nullable=False, default=TransactionStatus.PENDING
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    # внешние данные от банка
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    form_url: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # связь на пользователя и операцию
    # user = relationship("User", back_populates="payment_requests")
    operation = relationship("BalanceOperation", back_populates="payment_request", uselist=False)


Index("ix_payment_request_user_id", PaymentRequest.user_id)
Index("ix_payment_request_orderId", PaymentRequest.orderId)
Index("ix_payment_request_status", PaymentRequest.status)
Index("ix_payment_request_created_at", PaymentRequest.created_at)


@event.listens_for(PaymentRequest, "after_insert")
def generate_order_id(mapper, connection, target: PaymentRequest):
    order_id = f"ORD-{target.id:08d}"  # например ORD-00000042
    connection.execute(
        PaymentRequest.__table__.update()
        .where(PaymentRequest.id == target.id)
        .values(orderId=order_id)
    )

# === Логика, чтобы не забыть ===
# Всегда делать операцию в транзакции:
#
# Создать запись BalanceOperation со статусом PENDING.
#
# Попытаться обновить UserBalance.balance
#
# Если успех — установить balance_after и пометить BalanceOperation.status = COMPLETED. Иначе — FAILED.
#
# Для списаний проверять balance >= amount (или использовать reserved_balance при предварительной блокировке средств).
#
# В логике возвратов/рефандов создавать обратную операцию (direction противоположный) и помечать reference на оригинал.

