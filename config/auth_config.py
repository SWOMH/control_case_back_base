from datetime import timedelta
from pydantic_settings import BaseSettings
from typing import Optional


class AuthConfig(BaseSettings):
    """Конфигурация для авторизации JWT"""
    
    # JWT настройки
    SECRET_KEY: str = "0alL+0gKyNEIRdDdOC/3xC6MJWo4uDQz3QJD9AzZzAA" # Тестовый ключ (Пока пускай будет так, потом изменю) 
    ALGORITHM: str = "HS256"
    
    # Время жизни токенов
    ACCESS_TOKEN_EXPIRE_HOURS: int = 2  # 2 часа
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7  # 7 дней
    
    # Схема авторизации
    TOKEN_URL: str = "/api/auth/login"
    
    class Config:
        env_prefix = "AUTH_"
        case_sensitive = True


auth_config = AuthConfig()


def get_access_token_expire_delta() -> timedelta:
    """Возвращает время истечения access токена"""
    return timedelta(hours=auth_config.ACCESS_TOKEN_EXPIRE_HOURS)


def get_refresh_token_expire_delta() -> timedelta:
    """Возвращает время истечения refresh токена"""
    return timedelta(days=auth_config.REFRESH_TOKEN_EXPIRE_DAYS)
