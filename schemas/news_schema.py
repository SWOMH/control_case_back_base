from typing import Optional

from pydantic import BaseModel, Field, EmailStr, constr, field_validator
from datetime import datetime


class NewsResponse(BaseModel):
    id: int
    time_created: datetime
    title: str = Field(description='title')
    content: Optional[str] = Field(..., description='Контент(описание)')
    image_url: Optional[str] = Field(..., description='Ссылка на изображение')
    video_url: Optional[str] = Field(..., description='Ссылка на видео')
    comment_count: Optional[int] = Field(..., description='Кол-во комментариев')
    like_count: int = Field(description='Кол-во лайков')

    class Config:
        orm_mode = True