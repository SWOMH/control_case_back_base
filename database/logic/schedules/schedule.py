from datetime import date
from decimal import Decimal
from typing import Optional

from dateutil.relativedelta import relativedelta
from sqlalchemy import delete
from database.main_connection import DataBaseMainConnect
from database.decorator import connection
from sqlalchemy.orm import selectinload
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from database.logic.agreements.agreement import db_agreements
from database.models.agreement import AgreementClient
from database.models.schedule import PaymentSchedule, HistoryEditSchedule, StatusPayment
from exceptions.database_exc.schedule import ScheduleNotFound
from schemas.schedule_schema import ScheduleResponse
from exceptions.database_exc.agreement import AgreementNotFound


class SchedulePayments(DataBaseMainConnect):

    @connection
    async def get_all_schedule_by_id(self, agreement_id: int, session: AsyncSession) -> list[ScheduleResponse]:
        result = await session.execute(select(PaymentSchedule).where(PaymentSchedule.agreement_id == agreement_id))
        schedule = result.scalars().all()
        return schedule

    @connection
    async def generate_schedule(self, agreement_id: int, first_payment: Decimal | None, session: AsyncSession):
        """
        Генерирует график платежей для договора (только при заключении)
        """
        # Получаем данные договора
        agreement_data = await session.execute(
            select(AgreementClient).where(AgreementClient.id == agreement_id)
        )
        agreement = agreement_data.scalar_one_or_none()

        if agreement is None:
            raise AgreementNotFound

        # TODO: нужно переделать хуйню, ибо он удаляет график, а там оплаты могут быть
        # Удаляем существующий график платежей для этого договора
        await session.execute(
            delete(PaymentSchedule).where(PaymentSchedule.agreement_id == agreement_id)
        )

        # Определяем базовые параметры
        today = date.today()
        total_amount = agreement.price_after_discount if agreement.price_after_discount < \
                                                         agreement.price and agreement.price_after_discount != 0 \
            else agreement.price
        remaining_amount = total_amount

        # Обрабатываем первый платеж, если он есть
        if first_payment is not None and first_payment > 0:
            if first_payment >= remaining_amount:
                # Если первый платеж покрывает всю сумму
                schedule = PaymentSchedule(
                    agreement_id=agreement_id,
                    status=StatusPayment.PAID,
                    amount=remaining_amount,
                    date=today
                )
                session.add(schedule)
                await session.commit()
                return [schedule]

            # Создаем запись о первом платеже
            first_schedule = PaymentSchedule(
                agreement_id=agreement_id,
                status=StatusPayment.PAID,
                amount=first_payment,
                date=today
            )
            session.add(first_schedule)
            remaining_amount -= first_payment

        # Определяем количество платежей
        number_of_payments = agreement.number_of_payments

        # Рассчитываем сумму регулярного платежа
        regular_payment = remaining_amount / number_of_payments

        # Генерируем график платежей
        schedules = []
        payment_date = today

        for i in range(number_of_payments):
            # Добавляем месяц к дате, учитывая последние числа месяца
            if i > 0:
                payment_date = payment_date + relativedelta(months=1)
                # Корректируем дату, если в следующем месяце нет такого дня
                if payment_date.day != today.day:
                    payment_date = payment_date.replace(day=1) - relativedelta(days=1)

            # Для последнего платежа корректируем сумму, чтобы избежать ошибок округления
            amount = regular_payment if i < number_of_payments - 1 else remaining_amount

            schedule = PaymentSchedule(
                agreement_id=agreement_id,
                status=StatusPayment.EXPECTED,
                amount=amount,
                date=payment_date
            )
            session.add(schedule)
            schedules.append(schedule)
            remaining_amount -= amount

        await session.commit()
        return schedules


    # Тут еще не решил как сделать. Нужно зарисовать схему взаимодействия с беком, чтобы определиться как строить все платежи
    @connection(isolation_level='SERIALIZABLE')
    async def update_schedule_automatic(self, schedule: ScheduleResponse, session: AsyncSession) -> ScheduleResponse | Optional[ScheduleResponse]:
        """Меняет что-то в расписании (1 дату)"""
        schedule_b = await session.execute(
            select(PaymentSchedule).where(PaymentSchedule.id == int(schedule.id))
        )
        schedule_data = schedule_b.scalar_one_or_none()
        if schedule_data is None:
            raise ScheduleNotFound

        # сохраняем в историю (надо бы еще ссылку на человека сделать, кто изменил)
        schedule_history = HistoryEditSchedule(schedule_id=schedule_data.id,
                                               amount=schedule_data.amount,
                                               date=schedule_data.date,
                                               status=schedule_data.status,
                                               date_edit=date.today())
        session.add(schedule_history)

        schedule_data.date = schedule.date
        schedule_data.status = schedule.status
        schedule_data.amount = schedule.amount
        # оплаты я сюда не буду прикручивать. Пускай оно просто падает на баланс, а потом в день оплаты спишет само с баланса
        return schedule_data
