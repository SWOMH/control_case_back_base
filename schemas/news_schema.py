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


class NewsCreate(BaseModel):
    title: str = Field(description='title')
    content: Optional[str] = Field(None, description='Контент(описание)')
    image_url: Optional[str] = Field(None, description='Ссылка на изображение')
    video_url: Optional[str] = Field(None, description='Ссылка на видео')
    published: Optional[bool] = Field(True)
    time_published: Optional[datetime] = Field(None)

# Схема для обновления поста (все поля опциональны)
class NewsUpdate(BaseModel):
    title: Optional[str] = Field(None, description='title')
    content: Optional[str] = Field(None, description='Контент(описание)')
    image_url: Optional[str] = Field(None, description='Ссылка на изображение')
    video_url: Optional[str] = Field(None, description='Ссылка на видео')
    published: Optional[bool] = Field(None)
    moderated: Optional[bool] = Field(None)
    time_published: Optional[datetime] = Field(None)

# Схема ответа с полной информацией о посте
class NewsResponseAdmin(BaseModel):
    id: int
    title: str
    content: Optional[str]
    image_url: Optional[str]
    video_url: Optional[str]
    moderated: bool
    published: bool
    time_created: datetime
    time_updated: Optional[datetime]
    time_published: Optional[datetime]
    author_id: int

    class Config:
        from_attributes = True

# class NewsResponse(BaseModel):
#     id: int
#     title: str
#     content: Optional[str]
#     image_url: Optional[str]
#     video_url: Optional[str]
#     moderated: bool
#     published: bool
#     time_published: Optional[datetime]
#     author_id: int
#     time_created: datetime
#
#     class Config:
#         from_attributes = True
