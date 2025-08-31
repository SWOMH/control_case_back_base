from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List

from pydantic import BaseModel, Field


class AgreementBase(BaseModel):
    user_id: int
    date_conclusion: date = Field(description='Дата заключения договора')
    expected_completion_date: Optional[date] = Field(None, description='Предпологаемая дата окончания')
    end_date: Optional[date] = Field(description='Дата окончания')
    price: Decimal = Field(description='Цена договора')
    discount_amount: Optional[Decimal] = Field(None, description='Цена скидок')
    price_after_discount: Optional[Decimal] = Field(None, description='Цена договора после скидок')
    number_of_payments: int = Field(description='Кол-во платежей (заполняется сразу, потом можно будет изменить)')


class DiscountBase(BaseModel):
    discount_type: str = Field(description='Тип скидки')
    discount_amount: Decimal = Field(description='Сумма скидки')
    date_create: date = Field(description='Дата создания бонуса')
    active: bool = Field(default=True, description='Активен ли бонус')

class DiscountResponse(DiscountBase):
    id: int


class AgreementResponse(AgreementBase):
    id: int
    discount: Optional[List[DiscountResponse]]



