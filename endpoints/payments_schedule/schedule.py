from fastapi import APIRouter, HTTPException, Depends, status

from database.models.users import Users
from exceptions.database_exc.auth import UserNotFoundExists
from exceptions.database_exc.stage import StageNotFound
from schemas.court_schema import StageUpdateSchema, StageCreateSchema
from utils.permissions import require_admin_or_permission, get_current_active_user
from schemas.admin_schemas import Permissions
from database.logic.stages.stage import db_stage


router = APIRouter(prefix="/schedule", tags=["Расписание платежей"])