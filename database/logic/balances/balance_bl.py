from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from decimal import Decimal

from database.models.balance import BalanceOperation, PaymentRequest, TransactionDirection, TransactionStatus, UserBalance

async def create_payment(session: AsyncSession, user_id: int, amount: Decimal):
    # 1. Создаем PaymentRequest
    pr = PaymentRequest(
        user_id=user_id,
        amount=amount,
        status=TransactionStatus.PENDING
    )
    session.add(pr)
    await session.commit()          # чтобы сработал after_insert (генерация orderId)
    await session.refresh(pr)       # обновляем объект, чтобы получить orderId

    # 2. Запрашиваем у эквайринга платёж
    response = await tinkoff_api.init_payment(
        order_id=pr.orderId,
        amount=amount,
        return_url="https://myapp.ru/payment/callback"
    )

    # 3. Сохраняем formUrl и external_id (от банка)
    pr.form_url = response["formUrl"]
    pr.external_id = response.get("PaymentId")
    await session.commit()
    await session.refresh(pr)

    return pr.form_url

async def handle_payment_callback(session: AsyncSession, payload: dict):
    order_id = payload["OrderId"]
    status = payload["Status"]  # например, "CONFIRMED" или "FAILED"

    # 1. Находим PaymentRequest по orderId
    pr = await session.scalar(select(PaymentRequest).where(PaymentRequest.orderId == order_id))
    if not pr:
        raise ValueError("PaymentRequest not found")

    # 2. Обновляем статус
    if status == "CONFIRMED":
        pr.status = TransactionStatus.COMPLETED

        # 3. Создаём операцию в журнале (BalanceOperation)
        op = BalanceOperation(
            user_id=pr.user_id,
            operation_type_id=1,  # например, id "invoice_payment"
            direction=TransactionDirection.CREDIT,
            amount=pr.amount,
            status=TransactionStatus.COMPLETED,
            external_id=pr.external_id,
            payment_request=pr  # связываем напрямую через relationship
        )
        session.add(op)

        # 4. Обновляем баланс пользователя
        ub = await session.scalar(select(UserBalance).where(UserBalance.user_id == pr.user_id))
        if ub is None:
            # если запись не создана — создаём
            ub = UserBalance(user_id=pr.user_id, balance=Decimal("0.00"))
            session.add(ub)
            await session.flush()

        ub.balance += pr.amount
        ub.updated_at = datetime.now(timezone.utc)

    else:
        pr.status = TransactionStatus.FAILED

    await session.commit()
