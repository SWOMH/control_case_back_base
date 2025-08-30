from database.main_connection import DataBaseMainConnect
from database.models.court import Stage
from database.decorator import connection
from sqlalchemy.orm import selectinload
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.users import Users
from exceptions.database_exc.auth import UserNotFoundExists
from schemas.court_schema import StageUpdateSchema, StageCreateSchema, StageDeleteSchema
from exceptions.database_exc.stage import StageNotFound


class StageDataBase(DataBaseMainConnect):

    @connection
    async def get_stages_user(self, user_id: int, session: AsyncSession):
        return await session.execute(select(Stage).where(Stage.user_id == user_id))

    @connection
    async def upd_stage_user(self, upd_stage: StageUpdateSchema, session: AsyncSession) -> StageUpdateSchema:
        result = await session.execute(
            update(Stage)
            .where(Stage.id == upd_stage.id)
            .values(**upd_stage.dict(exclude_unset=True))
        )
        if result.rowcount == 0:
            raise StageNotFound
        await session.commit()

        return result

    @connection
    async def create_stage(self, stage: StageCreateSchema, session: AsyncSession) -> StageUpdateSchema:
        """
        Создает стадию для клиента
        """
        check_user = await session.execute(select(Users).where(Users.id == stage.user_id))
        if check_user.scalar_one_or_none() is None:
            raise UserNotFoundExists

        new_stage = Stage(
            user_id=stage.user_id,
            stage_name=stage.stage_name,
            description=stage.description,
            date_stage=stage.date_stage,
            appointed=stage.appointed,
            automatically=stage.automatically,
            appointed_employee=stage.appointed_employee,
            appointed_employee_id=stage.appointed_employee_id
        )
        session.add(new_stage)
        await session.commit()
        return new_stage

    @connection
    async def delete_stage_by_id(self, stage_id: id, session: AsyncSession):
        stage = await session.execute(select(Stage).where(Stage.id == stage_id))
        res = stage.scalar_one_or_none()
        if not res:
            raise StageNotFound
        session.delete(res)
        session.commit()


db_stage = StageDataBase()