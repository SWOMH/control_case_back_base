from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class UserBalanceOut(BaseModel):
    id: int
    balance: Decimal = Field(..., description="Текущий доступный баланс")
    reserved_balance: Decimal = Field(..., description="Зарезервированные средства")
    currency: str
    updated_at: datetime

    class Config:
        orm_mode = True

