from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer
import random

from config.redis import redis_db
from database.models.users import Users, Token
from database.logic.auth.auth import db_auth
from exceptions.database_exc.auth import UserNotFoundExists, UserBannedException, UserInvalidEmailOrPasswordException, \
    UserMailNotCorrectException, UserTokenNotFoundException, UserNotConfirmed
from schemas.user_schema import (
    UserRegister,
    UserLoginRequest,
    TokenResponse,
    UserUpdateRequest, UserResponse, RefreshTokenRequest
)
from utils.auth import (
    create_access_token,
    create_refresh_token,
    verify_token,
    get_current_active_user
)
from config.auth_config import get_access_token_expire_delta
from utils.tasks import send_confirmation_email

router = APIRouter(prefix="/auth", tags=["Авторизация"])
security = HTTPBearer()


@router.post("/register", response_model=UserRegister, status_code=status.HTTP_201_CREATED)
async def register_user(
        user_data: UserRegister
) -> UserResponse:
    """
    Регистрация нового пользователя
    """
    try:
        new_user = await db_auth.register_user(user_data)
    except UserMailNotCorrectException as e:
        raise HTTPException(
            status_code=404,
            detail=e.details
        )
    except UserNotConfirmed as e:
        raise HTTPException(
            status_code=406,
            detail=e.details
        )

    return UserResponse.model_validate(new_user)

@router.post('/confirmed_message_email', status_code=status.HTTP_200_OK)
async def send_message_confirmed(user_id: int):
    """
    Метод для отправки сообщения подтверждения пользователю
    на почту или телефон
    пока делаю под почту но потом прийдется выдумывать еще и с телефоном
    (буду использовать redis для хранения паролей)
    в бд они не нужны да и редис может чиститься по времени
    """
    code = random.randint(1000, 9999)
    user_email = await db_auth.get_user_by_id(user_id)
    redis_db.set(f'{user_id}_code_confirmed', f'{code}', 300)
    # send_confirmation_email.delay(user_email, code) # Тута отправляем сообщение
    send_confirmation_email(user_email, code)
    return {"message": "message send"}


@router.post('/code_acc', status_code=status.HTTP_200_OK)
async def message_confirmed(user_id: int, code: int):
    """
    Метод подтверждения регистрации
    Сравнивает коды и в случае совпадения делает аккаунт активированным
    """
    code_r = redis_db.get(f'{user_id}_code_confirmed')
    print(f'Получил код из редиса: {code_r}')
    if str(code) == code_r.decode('utf-8'):
        print('Коды совпали')
        await db_auth.activate_user(user_id)
        return {"message": "Account activated"}
    else:
        print(f'Коды не совпали {code} != {code_r}')
        return {"message": "Code not matched"}


@router.post("/login", response_model=TokenResponse)
async def login_user(
        login_data: UserLoginRequest
) -> TokenResponse:
    """
    Вход пользователя в систему

    Возвращает access и refresh токены
    """

    # Аутентифицируем пользователя
    try:
        user = await db_auth.authenticate_user(login_data.email, login_data.password)

    except UserInvalidEmailOrPasswordException as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=e.details,
            headers={"WWW-Authenticate": "Bearer"},
        )
    except UserNotFoundExists as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=e.details
        )

    # Создаем токены
    access_token_data = {"sub": str(user.id), "email": user.email}
    access_token = create_access_token(access_token_data)
    refresh_token = create_refresh_token(access_token_data)

    # Сохраняем токены в базе данных
    await db_auth.save_token(user.id, access_token, refresh_token)

    # Время жизни access токена в секундах
    expires_in = int(get_access_token_expire_delta().total_seconds())

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=expires_in
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
        refresh_data: RefreshTokenRequest
) -> TokenResponse:
    """
    Обновление access токена с помощью refresh токена
    """

    # Проверяем refresh токен
    token_data = verify_token(refresh_data.refresh_token, "refresh")

    if token_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный refresh токен",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user = await db_auth.user_verification_by_token(token_data.user_id, refresh_data.refresh_token)
    except UserTokenNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=e.details,
            headers={"WWW-Authenticate": "Bearer"},
        )
    except UserNotFoundExists as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=e.details
        )
    except UserBannedException as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=e.details
        )

    # Создаем новые токены
    access_token_data = {"sub": str(user.id), "email": user.email}
    new_access_token = create_access_token(access_token_data)
    new_refresh_token = create_refresh_token(access_token_data)

    # Обновляем токены в базе данных
    await db_auth.save_token(user.id, new_access_token, new_refresh_token)

    # Время жизни access токена в секундах
    expires_in = int(get_access_token_expire_delta().total_seconds())

    return TokenResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
        expires_in=expires_in
    )

@router.post("/password_reset_mail_send")
async def password_reset_mail_send(
        email: str) -> dict[str, str]:
    """
    Запрос сообщения на почту для сброса пароля
    """
    try:
        user = await db_auth.get_user_by_email(email)
    except UserNotFoundExists as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.details
        )
    code = random.randint(1000, 9999)
    redis_db.set(f'{user.id}_code_reset', f'{code}', 300)
    send_confirmation_email(user.login if user.login else user.email, code, 'reset_password')
    return {"message": "Code sent"}


@router.post("/password_reset_confirm_code")
async def password_reset_confirm(
        email: str,
        code: int
) -> dict[str, str]:
    """
    Подтверждение сброса пароля по коду
    """
    try:
        user = await db_auth.get_user_by_email(email)
    except UserNotFoundExists as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.details
        )
    code_r = redis_db.get(f'{user.id}_code_reset')
    if str(code) == code_r.decode('utf-8'):
        redis_db.set(f'{user.id}_reset_password_permission', 'True', 600)
        return {"message": "Password reset confirmed"}
    else:
        return {"message": "Code not matched"}


@router.post("/password_reset_confirm")
async def password_reset_confirm(
        email: str,
        new_password: str
) -> dict[str, str]:
    """
    Новый пароль после сброса пароля
    """
    try:
        user = await db_auth.get_user_by_email(email)
    except UserNotFoundExists as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.details
        )
    reset_password_permission = redis_db.get(f'{user.id}_reset_password_permission')
    if reset_password_permission is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password reset not confirmed"
        )
    await db_auth.update_user_password(user.id, new_password)
    return {"message": "Password reset confirmed"}


@router.post("/logout")
async def logout_user(
        current_user: Users = Depends(get_current_active_user)
):
    """
    Выход пользователя из системы (удаление токенов)
    """
    await db_auth.logout_user(current_user.id)

    return {"message": "Успешный выход из системы"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
        current_user: Users = Depends(get_current_active_user)
) -> UserResponse:
    """
    Получение информации о текущем пользователе
    """
    return UserResponse.model_validate(current_user)


# Эндпоинты управления пользователями
# @router.get("/users", response_model=UserListResponse)
# async def get_users_list(
#         # Фильтры закомментированы - фильтрация теперь на фронтенде
#         # search: str = None,
#         # restaurant_id: int = None,
#         # position_id: int = None,
#         # is_active: bool = None,
#         # is_admin: bool = None,
#         # trainee: bool = None,
#         # office_bool: bool = None,
#         limit: int = 1000,  # Большой лимит для загрузки всех данных
#         offset: int = 0,
#         current_user: Users = Depends(get_current_active_user)
# ) -> UserListResponse:
#     """
#     Получение списка пользователей
#
#     Администраторы видят всех пользователей,
#     менеджеры видят только сотрудников своего ресторана
#
#     Фильтрация выполняется на фронтенде для лучшей производительности
#     """
#     filters = UserListFilters(
#         # search=search,
#         # restaurant_id=restaurant_id,
#         # position_id=position_id,
#         # is_active=is_active,
#         # is_admin=is_admin,
#         # trainee=trainee,
#         # office_bool=office_bool,
#         limit=limit,
#         offset=offset
#     )
#
#     try:
#         users, total_count = await db_auth.get_users_list(filters, current_user)
#
#         return UserListResponse(
#             users=[UserResponse.model_validate(user) for user in users],
#             total_count=total_count,
#             offset=offset,
#             limit=limit
#         )
#     except Exception as e:
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail=f"Ошибка получения списка пользователей: {str(e)}"
#         )


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user_by_id(
        user_id: int,
        current_user: Users = Depends(get_current_active_user)
) -> UserResponse:
    """
    Получение пользователя по ID
    """
    try:
        user = await db_auth.get_user_by_id(user_id, current_user)
        return UserResponse.model_validate(user)
    except UserNotFoundExists as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.details
        )


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
        user_id: int,
        user_data: UserUpdateRequest,
        current_user: Users = Depends(get_current_active_user)
) -> UserResponse:
    """
    Обновление пользователя
    """
    try:
        updated_user = await db_auth.update_user(user_id, user_data, current_user)
        return UserResponse.model_validate(updated_user)
    except UserNotFoundExists as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.details
        )
    except UserMailNotCorrectException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.details
        )


@router.delete("/users/{user_id}")
async def delete_user(
        user_id: int,
        current_user: Users = Depends(get_current_active_user)
):
    """
    Деактивация пользователя (мягкое удаление)
    """
    try:
        await db_auth.delete_user(user_id, current_user)
        return {"message": "Пользователь успешно деактивирован"}
    except UserNotFoundExists as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.details
        )