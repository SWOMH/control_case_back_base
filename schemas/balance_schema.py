import enum
from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any

from pydantic import BaseModel, Field


class TransactionDirection(str, enum.Enum):
    CREDIT = "credit"
    DEBIT = "debit"


class TransactionStatus(str, enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"


class UserBalanceOut(BaseModel):
    balance: Decimal = Field(..., description="Текущий доступный баланс")
    reserved_balance: Decimal = Field(..., description="Зарезервированные средства")
    currency: str = Field(..., description="Валюта баланса")
    updated_at: datetime = Field(..., description="Время последнего обновления")

    class Config:
        orm_mode = True


class UserBalanceResponse(UserBalanceOut):
    id: int = Field(..., description="ID записи баланса")


class OperationTypeBase(BaseModel):
    code: str = Field(..., description="Код типа операции")
    title: str = Field(..., description="Название типа операции")
    direction: TransactionDirection = Field(..., description="Направление операции")
    description: Optional[str] = Field(None, description="Описание типа операции")


class OperationTypeResponse(OperationTypeBase):
    id: int = Field(..., description="ID типа операции")


class BalanceOperationBase(BaseModel):
    user_id: int = Field(..., description='ID пользователя')
    operation_type_id: int = Field(..., description='ID типа операции')
    direction: TransactionDirection = Field(..., description='Тип операции (пополнение/списание)')
    amount: Decimal = Field(..., gt=0, description='Сумма операции (положительное число)')
    currency: str = Field("RUB", description='Валюта операции')
    status: TransactionStatus = Field(TransactionStatus.COMPLETED, description='Статус операции')
    external_id: Optional[str] = Field(None, description='Внешний ID операции')
    reference_type: Optional[str] = Field(None, description='Тип ссылки')
    reference_id: Optional[str] = Field(None, description='ID ссылки')
    idempotency_key: Optional[str] = Field(None, description='Ключ идемпотентности')
    note: Optional[str] = Field(None, description='Примечание')
    metadata_json: Optional[Dict[str, Any]] = Field(None, description='Метаданные в формате JSON')

    class Config:
        orm_mode = True


class BalanceOperationCreate(BalanceOperationBase):
    pass


class BalanceOperationResponse(BalanceOperationBase):
    id: int = Field(..., description='ID операции')
    balance_after: Optional[Decimal] = Field(None, description='Баланс после операции')
    created_at: datetime = Field(..., description='Время создания операции')
    updated_at: datetime = Field(..., description='Время обновления операции')


class BalanceOperationUpdate(BaseModel):
    status: Optional[TransactionStatus] = Field(None, description='Статус операции')
    balance_after: Optional[Decimal] = Field(None, description='Баланс после операции')
    note: Optional[str] = Field(None, description='Примечание')
    metadata_json: Optional[Dict[str, Any]] = Field(None, description='Метаданные в формате JSON')