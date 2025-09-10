from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import time


class GroupCreateRequest(BaseModel):
    """Схема для создания группы"""
    name: str = Field(..., min_length=2, max_length=100, description="Название группы")


class GroupResponse(BaseModel):
    """Схема ответа с информацией о группе"""
    id: int
    name: str

    class Config:
        from_attributes = True


class GroupUpdateRequest(BaseModel):
    """Схема для обновления группы"""
    name: Optional[str] = Field(None, min_length=2, max_length=100, description="Новое название группы")


class UserGroupRequest(BaseModel):
    """Схема для добавления/удаления пользователя в группу"""
    user_id: int = Field(..., description="ID пользователя")
    group_id: int = Field(..., description="ID группы")


class GroupPermissionRequest(BaseModel):
    """Схема для управления правами доступа группы"""
    group_id: int = Field(..., description="ID группы")
    permissions: List[str] = Field(..., description="Список прав доступа")


class GroupPermissionResponse(BaseModel):
    """Схема ответа с правами доступа группы"""
    group_id: int
    permissions: List[str]


# Константы для прав доступа
class Permissions:
    """Константы прав доступа"""
    CREATE_NEWS = 'create_news'
    UPDATE_NEWS = 'update_news'
    DELETE_NEWS = 'delete_news'
    MODERATED_NEWS = 'moderated_news'

    # Управление пользователями
    CREATE_USER = "create_user"
    UPDATE_USER = "update_user"
    DELETE_USER = "delete_user"
    VIEW_USER = "view_user"

    # Управление юристами
    VIEW_USER_LAWYER = "view_user_lawyer"
    CREATE_USER_LAWYER = "create_user_lawyer"
    UPDATE_USER_LAWYER = "update_user_lawyer"
    DELETE_USER_LAWYER = "delete_user_lawyer"

    # Управление продажниками/поддержкой
    VIEW_USER_SALESMAN = "view_user_salesman"
    CREATE_USER_SALESMAN = "create_user_salesman"
    UPDATE_USER_SALESMAN = "update_user_salesman"
    DELETE_USER_SALESMAN = "delete_user_salesman"

    # Управление документами
    CREATE_DOCUMENTS = 'create_documents'
    UPDATE_DOCUMENTS = "update_documents"
    DELETE_DOCUMENTS = "delete_documents"

    # Управление группами
    CREATE_GROUP = "create_group"
    UPDATE_GROUP = "update_group"
    DELETE_GROUP = "delete_group"
    VIEW_GROUP = "view_group"
    MANAGE_GROUP_PERMISSIONS = "manage_group_permissions"

    # Управление Стадиями
    READ_ALL_STAGE = 'read_all_stage'
    CREATE_STAGE = 'create_stage'
    UPDATE_STAGE = 'update_stage'
    DELETE_STAGE = 'delete_stage'

    # Управление бонусами
    CREATE_BONUS = "create_bonus"
    UPDATE_BONUS = "update_bonus"
    DELETE_BONUS = "delete_bonus"
    VIEW_BONUS = "view_bonus"
    CREATE_BONUSES_TYPE = "create_bonuses_type"
    UPDATE_BONUSES_TYPE = "update_bonuses_type"
    DELETE_BONUSES_TYPE = "delete_bonuses_type"
    VIEW_BONUSES_TYPE = "view_bonuses_type"

    # Управление вычетами
    CREATE_DEDUCTION = "create_deduction"
    UPDATE_DEDUCTION = "update_deduction"
    DELETE_DEDUCTION = "delete_deduction"
    VIEW_DEDUCTION = "view_deduction"
    CREATE_DEDUCTION_TYPE = "create_deduction_type"
    UPDATE_DEDUCTION_TYPE = "update_deduction_type"
    DELETE_DEDUCTION_TYPE = "delete_deduction_type"
    VIEW_DEDUCTION_TYPE = "view_deduction_type"
    # Все права (для удобства)
    ALL_PERMISSIONS = [
        CREATE_NEWS, UPDATE_NEWS, DELETE_NEWS,
        VIEW_USER_LAWYER, CREATE_USER_LAWYER, UPDATE_USER_LAWYER, DELETE_USER_LAWYER,
        VIEW_USER_SALESMAN, CREATE_USER_SALESMAN, UPDATE_USER_SALESMAN, DELETE_USER_SALESMAN,
        CREATE_DOCUMENTS, UPDATE_DOCUMENTS, DELETE_DOCUMENTS,
        CREATE_USER, UPDATE_USER, DELETE_USER, VIEW_USER,
        CREATE_GROUP, UPDATE_GROUP, DELETE_GROUP, VIEW_GROUP, MANAGE_GROUP_PERMISSIONS,
        CREATE_BONUS, UPDATE_BONUS, DELETE_BONUS, VIEW_BONUS,
        CREATE_DEDUCTION, UPDATE_DEDUCTION, DELETE_DEDUCTION, VIEW_DEDUCTION,
        READ_ALL_STAGE, CREATE_STAGE, UPDATE_STAGE, DELETE_STAGE,
        CREATE_BONUSES_TYPE, UPDATE_BONUSES_TYPE, DELETE_BONUSES_TYPE,
        VIEW_BONUSES_TYPE, VIEW_DEDUCTION_TYPE,
        CREATE_DEDUCTION_TYPE, UPDATE_DEDUCTION_TYPE, DELETE_DEDUCTION_TYPE
    ]