from typing import Set
from fastapi import HTTPException, status, Depends

from database.logic.permissions import db_permissions
from database.models.users import Users, Group, user_group_association, group_permission_association
from utils.auth import get_current_active_user
from schemas.admin_schemas import  Permissions


async def get_user_permissions(user: Users) -> Set[str]:
    """Получает все права доступа пользователя"""

    # Если пользователь админ - у него есть все права
    if user.is_admin:
        return set(Permissions.ALL_PERMISSIONS)

    permissions = await db_permissions.get_all_permissions(user)

    return permissions


async def check_permission(
        required_permission: str,
        current_user: Users = Depends(get_current_active_user)
) -> Users:
    """Проверяет, есть ли у пользователя требуемое право доступа"""

    # Если пользователь админ - разрешаем все
    if current_user.is_admin:
        return current_user

    # Получаем права пользователя
    user_permissions = await get_user_permissions(current_user)

    # Проверяем наличие требуемого права
    if required_permission not in user_permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Недостаточно прав доступа. Требуется право: {required_permission}"
        )

    return current_user


def require_permission(permission: str):
    """Декоратор для проверки прав доступа"""

    async def permission_checker(
            current_user: Users = Depends(get_current_active_user)
    ) -> Users:
        return await check_permission(permission, current_user)

    return permission_checker


async def check_admin_or_permission(
        required_permission: str,
        current_user: Users = Depends(get_current_active_user)
) -> Users:
    """Проверяет, является ли пользователь админом или имеет требуемое право"""

    if current_user.is_admin:
        return current_user

    return await check_permission(required_permission, current_user)


def require_admin_or_permission(permission: str):
    """Декоратор для проверки админа или конкретного права"""

    async def admin_or_permission_checker(
            current_user: Users = Depends(get_current_active_user)
    ) -> Users:
        return await check_admin_or_permission(permission, current_user)

    return admin_or_permission_checker


async def is_admin(current_user: Users = Depends(get_current_active_user)) -> Users:
    """Проверяет, является ли пользователь администратором"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Требуются права администратора"
        )
    return current_user


def require_admin():
    """Декоратор для проверки прав администратора"""
    return is_admin