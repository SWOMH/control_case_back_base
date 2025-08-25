from database.main_connection import DataBaseMainConnect
from database.decorator import connection
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, insert, and_
from exceptions.database_exc.group_exceptions import GroupAlreadyExistsException, GroupNotFoundException, UserFoundInGroupException, \
    UserNotInGroupException
from exceptions.database_exc.auth import UserNotFoundExists, UserNotPermissionsException
from schemas.admin_schemas import GroupCreateRequest, GroupPermissionRequest, GroupUpdateRequest, Permissions, \
    UserGroupRequest
from database.models.users import Group, Users, user_group_association, group_permission_association


class DatabasePermissions(DataBaseMainConnect):

    @connection
    async def get_all_permissions(self, user: Users, session: AsyncSession):
        """
        Получение всех прав для каждой группы пользователя
        """
        permissions = set()

        # Получаем все группы пользователя
        stmt = select(Group).join(
            user_group_association,
            Group.id == user_group_association.c.group_id
        ).where(
            user_group_association.c.user_id == user.id,
            user_group_association.c.active == True
        )

        result = await session.execute(stmt)
        user_groups = result.scalars().all()

        # Получаем права для каждой группы
        for group in user_groups:
            group_permissions_stmt = select(group_permission_association.c.permission).where(
                group_permission_association.c.group_id == group.id
            )
            group_permissions_result = await session.execute(group_permissions_stmt)
            group_permissions = group_permissions_result.scalars().all()
            permissions.update(group_permissions)

        return permissions


db_permissions = DatabasePermissions()