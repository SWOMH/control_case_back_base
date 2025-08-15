from typing import Optional
from datetime import datetime
from pydantic import BaseModel


class CourtStageOut(BaseModel):
    """
    Заглушка для 'стадий в суде'.
    Пока по ним не все решено, потом переделаю
    """
    id: int
    case_id: Optional[int] = None
    stage_name: str
    status: Optional[str] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None

    class Config:
        orm_mode = True