from fastapi import APIRouter, HTTPException, Depends, status

from database.models.users import Users
from exceptions.database_exc.auth import UserNotFoundExists
from exceptions.database_exc.stage import StageNotFound
from schemas.court_schema import StageUpdateSchema, StageCreateSchema
from utils.permissions import require_admin_or_permission, get_current_active_user
from schemas.admin_schemas import Permissions
from database.logic.stages.stage import db_stage


router = APIRouter(prefix="/stage", tags=["Стадии"])


@router.get(response_model=list[StageUpdateSchema], status_code=status.HTTP_200_OK)
async def get_all_stage(user: Users = Depends(get_current_active_user)):
    all_stage = await db_stage.get_stages_user(user.id)
    if all_stage is None:
        return HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='stage is empty',
            headers={"WWW-Authenticate": "Bearer"},
        )
    return StageUpdateSchema.model_validate(all_stage)


@router.post(response_model=StageUpdateSchema, status_code=status.HTTP_201_CREATED)
async def create_stage(stage: StageCreateSchema,
                       user: Users = Depends(require_admin_or_permission(Permissions.CREATE_STAGE))):
    try:
        new_stage = await db_stage.create_stage(stage)
        return StageUpdateSchema.model_validate(new_stage)
    except UserNotFoundExists as e:
        return HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=e.details,
            headers={"WWW-authenticate": "Bearer"}
        )


@router.post('/update', response_model=StageUpdateSchema)
async def update_stage(stage: StageUpdateSchema,
                       user: Users = Depends(require_admin_or_permission(Permissions.UPDATE_STAGE)))\
        -> StageUpdateSchema | HTTPException:
    try:
        up_stage = await db_stage.upd_stage_user(stage)
        return up_stage
    except StageNotFound as e:
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.details,
            headers={"WWW-authenticate": "Bearer"}
        )


@router.post('/delete', status_code=status.HTTP_200_OK)
async def delete_stage(stage_id: int,
                       user: Users = Depends(require_admin_or_permission(Permissions.DELETE_STAGE))):
    try:
        await db_stage.delete_stage_by_id(stage_id)
        return status.HTTP_200_OK
    except StageNotFound as e:
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.details,
            headers={"WWW-authenticate": "Bearer"}
        )
