from typing import Optional
from datetime import datetime
from pydantic import BaseModel


class StageCreateSchema(BaseModel):
    user_id: int
    stage_name: str
    description: Optional[str]
    date_stage: datetime
    appointed: Optional[str]
    automatically: bool
    appointed_employee: str
    appointed_employee_id: Optional[int]

    class Config:
        orm_mode = True


class StageUpdateSchema(StageCreateSchema):
    id: int


class StageDeleteSchema(BaseModel):
    stage_id: int
