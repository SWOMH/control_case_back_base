from database.main_connection import DataBaseMainConnect
from database.decorator import connection
from sqlalchemy.orm import selectinload
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from database.models.agreement import AgreementClient, Discount, DiscountAssociation
from database.models.users import Users
from exceptions.database_exc.auth import UserNotFoundExists
from schemas.agreement_schema import AgreementResponse
from schemas.court_schema import StageUpdateSchema, StageCreateSchema, StageDeleteSchema
from exceptions.database_exc.stage import StageNotFound


class AgreementsDatabaseLogic(DataBaseMainConnect):

    @connection
    async def get_all_agreements_full_info_by_user_id(self, user_id: int, session: AsyncSession) -> list[AgreementResponse] | AgreementResponse:
        """
        Получение всех договоров пользователя со всеми связанными скидками
        Возвращает список договоров с информацией о скидках
        """
        query = (
            select(AgreementClient)
            .where(AgreementClient.user_id == user_id)
            .options(
                selectinload(AgreementClient.discount_associations)
                .selectinload(DiscountAssociation.discount)
            )
        )
        result = await session.execute(query)
        agreements = result.scalars().all()

        return agreements

    @connection
    async def get_all_agreements_by_user_id(self, user_id: int, session: AsyncSession) -> list[AgreementResponse] | AgreementResponse:
        """
        Получение только договоров пользователя без информации о скидках
        """
        query = select(AgreementClient).where(AgreementClient.user_id == user_id)
        result = await session.execute(query)
        agreements = result.scalars().all()

        return agreements

    @connection
    async def get_agreement_all_info_by_agreement_id(self, agreement_id: int, session: AsyncSession) -> list[
                                                                                                  AgreementResponse] | AgreementResponse:
        """
        Получение договора пользователя со всеми связанными скидками
        Возвращает договор с информацией о скидках
        """
        query = (
            select(AgreementClient)
            .where(AgreementClient.id == agreement_id)
            .options(
                selectinload(AgreementClient.discount_associations)
                .selectinload(DiscountAssociation.discount)
            )
        )
        result = await session.execute(query)
        agreements = result.scalars().all()

        return agreements

    @connection
    async def get_agreement_only_by_agreement_id(self, agreement_id: int, session: AsyncSession) -> list[
                                                                                              AgreementResponse] | AgreementResponse:
        """
        Получение пользователя без информации о скидках
        """
        query = select(AgreementClient).where(AgreementClient.id == agreement_id)
        result = await session.execute(query)
        agreements = result.scalars().all()

        return agreements

    # === Если будет проблема из-за relation
    # @connection
    # async def get_agreement_all_info(self, user_id: int, session: AsyncSession):
    #     """
    #     Альтернативная реализация без использования отношений в моделях
    #     """
    #     query = (
    #         select(
    #             AgreementClient,
    #             DiscountAssociation,
    #             Discount
    #         )
    #         .join(DiscountAssociation, AgreementClient.id == DiscountAssociation.agreement_id)
    #         .join(Discount, DiscountAssociation.discount_id == Discount.id)
    #         .where(AgreementClient.user_id == user_id)
    #     )
    #
    #     result = await session.execute(query)
    #     rows = result.all()
    #
    #     # Группируем результаты по договорам
    #     agreements_dict = {}
    #     for agreement, association, discount in rows:
    #         if agreement.id not in agreements_dict:
    #             agreements_dict[agreement.id] = {
    #                 'agreement': agreement,
    #                 'discounts': []
    #             }
    #         agreements_dict[agreement.id]['discounts'].append({
    #             'association': association,
    #             'discount': discount
    #         })
    #
    #     return list(agreements_dict.values())


db_agreements = AgreementsDatabaseLogic()
