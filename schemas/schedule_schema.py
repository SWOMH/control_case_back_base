from datetime import date
from decimal import Decimal
from typing import Optional

from database.models.schedule import StatusPayment
from pydantic import BaseModel, Field


class ScheduleBase(BaseModel):
    agreement_id: int = Field(description='id Договора клиента')
    status: StatusPayment = Field(default=StatusPayment.EXPECTED, description='Статус платежа')
    deducted_id: Optional[int] = Field(None, description='Id Скидки')
    amount: Decimal = Field(description='Сумма платежа в этот месяц')
    date: date = Field(description='Дата платежа')


class HistoryEditScheduleBase(BaseModel):
    """Тут будет история изменений расписания платежей"""
    schedule_id: int = Field(description='id на запись рассписания')
    amount: Decimal = Field(description='Сумма платежа в этот месяц')
    date: date = Field(description='Дата платежа')
    status: StatusPayment = Field(default=StatusPayment.EXPECTED, description='Статус платежа')
    date_edit: date = Field(description='Дата когда внесли изменения в основную таблицу')


class ScheduleResponse(ScheduleBase):
    id: int


class HistoryEditScheduleResponse(HistoryEditScheduleBase):
    id: int
