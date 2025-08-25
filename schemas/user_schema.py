from typing import Optional, List, Dict
from datetime import datetime, date
from schemas.balance_schema import UserBalanceOut
from schemas.court_schema import CourtStageOut

from pydantic import BaseModel, Field, EmailStr, constr, field_validator

# ---------------------------
# Схемы для запроса регистрации
# ---------------------------
class UserRegister(BaseModel):
    """
    Схема для регистрации.
    При регистрации достаточно: ФИО, логин, пароль, locale, timezone.
    """
    login: constr(min_length=6, max_length=254)
    password: constr(min_length=8, max_length=128)
    first_name: Optional[constr(max_length=150)] = None
    surname: Optional[constr(max_length=150)] = None
    patronymic: Optional[constr(max_length=150)] = None
    locale: Optional[constr(max_length=10)] = None
    timezone: Optional[constr(max_length=64)] = None

    @field_validator("password")
    def password_strength(cls, v: str) -> str:
        # простая проверка — можно расширить
        if v.islower() or v.isupper() or v.isnumeric():
            raise ValueError("Пароль должен содержать сочетание букв верхнего/нижнего регистра и цифр")
        return v


class UserLoginRequest(BaseModel):
    """Схема для входа пользователя"""
    email: EmailStr = Field(..., description="Email пользователя")
    password: str = Field(..., description="Пароль пользователя")


# По желанию: схема ответа при успешной регистрации (не содержит пароль)
class UserRegisterResponse(BaseModel):
    access_token: str = Field(..., description="Access токен")
    refresh_token: str = Field(..., description="Refresh токен")
    token_type: str = Field(default="bearer", description="Тип токена")
    expires_in: int = Field(..., description="Время жизни access токена в секундах")

    class Config:
        orm_mode = True

class GroupOut(BaseModel):
    id: int
    name: str

    class Config:
        orm_mode = True


class TokenData(BaseModel):
    """Схема данных токена для внутреннего использования"""
    user_id: Optional[int] = None
    email: Optional[str] = None


# ---------------------------
# Полная схема ответа с информацией о пользователе
# ---------------------------
class UserOut(BaseModel):
    id: int
    login: str
    email: Optional[EmailStr] = None
    surname: Optional[str] = None
    first_name: Optional[str] = None
    patronymic: Optional[str] = None

    is_client: bool = False
    is_active: bool = True
    is_staff: bool = False
    is_support: bool = False
    is_banned: bool = False
    is_lawyer: bool = False

    last_activity: Optional[datetime] = None
    last_login: Optional[datetime] = None
    # created_at: datetime
    # updated_at: datetime
    deleted_at: Optional[datetime] = None

    locale: Optional[str] = None
    timezone: Optional[str] = None
    preferences: Optional[Dict] = None

    # вложенные сущности
    groups: List[GroupOut] = []
    balance: Optional[UserBalanceOut] = None
    # court_stages: List[CourtStageOut] = []

    class Config:
        orm_mode = True

class UserUpdateRequest(BaseModel):
    """
    Схема для обновления пользователя
    """
    email: Optional[EmailStr] = Field(None, description="Email пользователя")
    password: Optional[str] = Field(None, min_length=6, description="Новый пароль пользователя")
    surname: Optional[str] = Field(None, min_length=2, description="Фамилия")
    full_name: Optional[str] = Field(None, min_length=2, description="Имя пользователя")
    patronymic: Optional[str] = Field(None, min_length=2, description="Отчество")
    # phone: Optional[str] = Field(None, description="Телефон пользователя")

    is_client: Optional[bool] = Field(None, description='Клиент или нет')
    is_active: Optional[bool] = Field(None, description="Активен ли пользователь")
    is_banned: Optional[bool] = Field(None, description="Заблокирован ли пользователь")
    date_termination: Optional[date] = Field(None, description="Дата увольнения")
    groups: Optional[list[str]] = Field(None, description="Группы пользователя")
