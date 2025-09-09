from enum import Enum

from pydantic import BaseModel, Field


class TypeUpdSchedule(str, Enum):
    EACH_PAYMENT = 'each_payment'  # С каждого платежа убирать
    ONE_PAYMENT = 'one_payment'  # С одного платежа


class AppSettings(BaseModel):
    automatic_upd_schedule: bool = Field(description='Автоматически обновлять расписание или это будет делать только '
                                                     'оператор. (True - автоматически',
                                         default=True)
    type_upd_schedule: TypeUpdSchedule = Field(description='В случае переплаты по платежу как действовать в '
                                                           'автоматическом режиме. Сверх снять с каждого платежа в '
                                                           'графике или только с последнего?',
                                               default=TypeUpdSchedule.EACH_PAYMENT)

