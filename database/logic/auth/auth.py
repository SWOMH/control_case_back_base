from typing import Optional

from sqlalchemy.orm import selectinload

from database.main_connection import DataBaseMainConnect
from database.decorator import connection
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from utils.auth import get_password_hash, verify_password
from database.models.users import Users, Group, Token
from exceptions.database_exc.auth import UserNotFoundExists, UserMailNotCorrectException, \
    UserBannedException, UserNotPermissionsException, UserTokenNotFoundException, UserAlreadyExistsException, \
    UserInvalidEmailOrPasswordException, UserPasswordNotCorrectException, UserNotConfirmed
from schemas.user_schema import UserRegister, UserUpdateRequest


class AuthUsers(DataBaseMainConnect):

    @connection()
    async def register_user(self, user_data: UserRegister, session: AsyncSession):
        """
        Регистрация пользователя

        - **email**: Email пользователя (используется как логин)
        - **password**: Пароль пользователя (минимум 6 символов)
        - **first_name**: Имя пользователя
        - **surname**: Фамилия
        - **patronymic**: Отчество
        """
        stmt = select(Users).where(Users.email == user_data.login)
        result = await session.execute(stmt)
        existing_user = result.scalar_one_or_none()
        if existing_user:
            if existing_user.account_confirmed:
                raise UserAlreadyExistsException
            if not existing_user.account_confirmed:
                raise UserNotConfirmed


        # Хешируем пароль
        hashed_password = get_password_hash(user_data.password)

        new_user = Users(
            login=user_data.login,
            password=hashed_password,
            first_name=user_data.first_name,
            surname=user_data.surname,
            patronymic=user_data.patronymic,
            locale=user_data.locale,
            timezone=user_data.timezone
        )

        session.add(new_user)
        await session.commit()
        await session.refresh(new_user)
        return new_user

    @connection()
    async def authenticate_user(self, login: str, password: str, session: AsyncSession) -> Optional[Users]:
        """Аутентифицирует пользователя"""
        stmt = select(Users).where(Users.login == login)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            raise UserNotFoundExists

        if not verify_password(password, user.password):
            raise UserInvalidEmailOrPasswordException

        return user

    @connection()
    async def save_token(self, user_id: int, access_token: str, refresh_token: str, session: AsyncSession):
        """Сохраняет токены в базе данных"""
        # Удаляем старые токены пользователя
        await session.execute(
            select(Token).where(Token.user_id == user_id)
        )
        old_tokens = await session.execute(select(Token).where(Token.user_id == user_id))
        for token in old_tokens.scalars():
            await session.delete(token)

        # Создаем новый токен
        new_token = Token(
            user_id=user_id,
            token=access_token,
            refresh_token=refresh_token
        )
        session.add(new_token)
        await session.commit()

    @connection()
    async def user_verification_by_token(self, token_user_id: int, refresh_token: str, session: AsyncSession) -> Users:
        """
        Верификация пользователя по токену
        """
        # Проверяем, что токен существует в базе данных
        stmt_token = select(Token).where(
            Token.user_id == token_user_id,
            Token.refresh_token == refresh_token
        )
        result = await session.execute(stmt_token)
        db_token = result.scalar_one_or_none()
        if not db_token:
            raise UserTokenNotFoundException

        # Получаем пользователя
        stmt = select(Users).options(selectinload(Users.balance)).where(
            Users.id == token_user_id)
        result = await session.execute(stmt)
        user: Users = result.scalar_one_or_none()

        if not user:
            raise UserNotFoundExists

        if user.is_banned:
            raise UserBannedException

        return user

    @connection()
    async def user_get_by_token(self, token_user_id: int, session: AsyncSession) -> Users:
        """
        Поиск пользователя по токену
        """
        # Получаем пользователя
        # stmt = select(Users).options(selectinload(Users.balance), selectinload(Users.groups)).where(
        #     Users.id == token_user_id)
        stmt = select(Users).options(selectinload(Users.groups)).where(
            Users.id == token_user_id)
        result = await session.execute(stmt)
        user: Users = result.scalar_one_or_none()

        if not user:
            raise UserNotFoundExists

        if user.is_banned:
            raise UserBannedException

        return user

    @connection()
    async def logout_user(self, user_id: int, session: AsyncSession):
        # Удаляем все токены пользователя
        stmt = select(Token).where(Token.user_id == user_id)
        result = await session.execute(stmt)
        tokens = result.scalars().all()

        for token in tokens:
            await session.delete(token)

        await session.commit()

    # @connection
    # async def get_users_list(self, filters: UserListFilters, current_user: Users, session: AsyncSession) -> Tuple[
    #     list[Users], int]:
    #     """
    #     Получение списка пользователей с фильтрацией и пагинацией
    #     """
    #     # Базовый запрос с загрузкой связанных данных
    #     stmt = select(Users).options(
    #         selectinload(Users.restaurant),
    #         selectinload(Users.office),
    #         selectinload(Users.position),
    #         selectinload(Users.groups)
    #     )
    #
    #     # Фильтры доступа: менеджер видит только своих сотрудников
    #     if not current_user.is_admin:
    #         if current_user.restaurant_id:
    #             stmt = stmt.where(Users.restaurant_id == current_user.restaurant_id)
    #         else:
    #             # Если у менеджера нет ресторана, он не видит никого
    #             stmt = stmt.where(Users.id == -1)  # Невозможное условие
    #
    #     # Применяем фильтры
    #     if filters.search:
    #         search_filter = or_(
    #             Users.full_name.ilike(f"%{filters.search}%"),
    #             Users.email.ilike(f"%{filters.search}%"),
    #             Users.phone.ilike(f"%{filters.search}%"),
    #             Users.tab_number.ilike(f"%{filters.search}%")
    #         )
    #         stmt = stmt.where(search_filter)
    #
    #     if filters.restaurant_id is not None:
    #         stmt = stmt.where(Users.restaurant_id == filters.restaurant_id)
    #
    #     if filters.position_id is not None:
    #         stmt = stmt.where(Users.position_id == filters.position_id)
    #
    #     if filters.is_active is not None:
    #         stmt = stmt.where(Users.is_active == filters.is_active)
    #
    #     if filters.is_admin is not None:
    #         stmt = stmt.where(Users.is_admin == filters.is_admin)
    #
    #     if filters.trainee is not None:
    #         stmt = stmt.where(Users.trainee == filters.trainee)
    #
    #     if filters.office_bool is not None:
    #         stmt = stmt.where(Users.office_bool == filters.office_bool)
    #
    #     # Подсчет общего количества
    #     count_stmt = select(func.count()).select_from(stmt.subquery())
    #     count_result = await session.execute(count_stmt)
    #     total_count = count_result.scalar()
    #
    #     # Применяем пагинацию и сортировку
    #     stmt = stmt.order_by(Users.full_name).offset(filters.offset).limit(filters.limit)
    #
    #     # Выполняем запрос
    #     result = await session.execute(stmt)
    #     users = result.scalars().all()
    #
    #     return users, total_count

    @connection()
    async def get_user_by_id(self, user_id: int, current_user: Users, session: AsyncSession) -> Users:
        """
        Получение пользователя по ID с проверкой доступа
        """
        stmt = select(Users).options(
            selectinload(Users.balance),
            selectinload(Users.groups)
        ).where(Users.id == user_id)

        # Фильтры доступа: менеджер видит только своих сотрудников
        # if not current_user.is_admin:
        #     if current_user.restaurant_id:
        #         stmt = stmt.where(Users.restaurant_id == current_user.restaurant_id)
        #     else:
        #         raise UserNotFoundExists

        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            raise UserNotFoundExists

        return user

    @connection()
    async def update_user(self, user_id: int, user_data: UserUpdateRequest, current_user: Users,
                          session: AsyncSession) -> Users:
        """
        Обновление пользователя
        """
        # Получаем пользователя с проверкой доступа
        user = await self.get_user_by_id(user_id, current_user, session)

        # Проверяем email на уникальность (если он изменяется)
        if user_data.email and user_data.email != user.email:
            stmt = select(Users).where(Users.email == user_data.email, Users.id != user_id)
            result = await session.execute(stmt)
            existing_user = result.scalar_one_or_none()
            if existing_user:
                raise UserMailNotCorrectException

        # Обновляем поля
        update_data = user_data.model_dump(exclude_unset=True)

        # Хешируем пароль если он изменяется
        if 'password' in update_data:
            update_data['password'] = get_password_hash(update_data['password'])

        # Обрабатываем группы отдельно
        groups_data = update_data.pop('groups', None)

        # Обновляем основные поля
        for field, value in update_data.items():
            setattr(user, field, value)

        # Обновляем группы
        if groups_data is not None:
            stmt = select(Group).where(Group.id.in_(groups_data))
            result = await session.execute(stmt)
            groups = result.scalars().all()
            user.groups = groups


        await session.commit()
        await session.refresh(user)
        return user

    @connection()
    async def activate_user(self, user_id: int, session: AsyncSession):
        """
        Активирует пользователя
        """
        stmt = select(Users).options(
            selectinload(Users.balance),
            selectinload(Users.groups)
        ).where(Users.id == user_id)

        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            raise UserNotFoundExists

        user.account_confirmed = True
        await session.commit()


    @connection()
    async def delete_user(self, user_id: int, current_user: Users, session: AsyncSession) -> bool:
        """
        Мягкое удаление пользователя (деактивация)
        """
        # Получаем пользователя с проверкой доступа
        user = await self.get_user_by_id(user_id, current_user, session)

        # Деактивируем пользователя
        user.is_active = False

        # Удаляем все токены пользователя
        stmt = select(Token).where(Token.user_id == user_id)
        result = await session.execute(stmt)
        tokens = result.scalars().all()

        for token in tokens:
            await session.delete(token)

        await session.commit()
        return True


db_auth = AuthUsers()
