from datetime import date
from decimal import Decimal
from dateutil.relativedelta import relativedelta
from sqlalchemy import delete

from database.main_connection import DataBaseMainConnect
from database.decorator import connection
from sqlalchemy.orm import selectinload
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from database.logic.agreements.agreement import db_agreements
from database.models.schedule import PaymentSchedule, HistoryEditSchedule, StatusPayment
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
        Генерирует график платежей для договора
        """
        # Получаем данные договора
        agreement_data = await session.execute(
            select(AgreementClient).where(AgreementClient.id == agreement_id)
        )
        agreement = agreement_data.scalar_one_or_none()

        if agreement is None:
            raise AgreementNotFound

        # Удаляем существующий график платежей для этого договора
        await session.execute(
            delete(PaymentSchedule).where(PaymentSchedule.agreement_id == agreement_id)
        )

        # Определяем базовые параметры
        today = date.today()
        total_amount = agreement.price_after_discount or agreement.price
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

        # Определяем количество платежей (это поле должно быть в вашей модели)
        # Если его нет, нужно добавить в AgreementClient
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


