from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime
from datetime import date



class ChatMessageRequest(BaseModel):
    """
    Схема для запроса чата с поддержкой
    """
    id: int = Field(..., description='id пользователя')
    

class ChatMessagesResponse(BaseModel):
    """
    Схема ответа пользователя после регистрации
    """
    id: int = Field(..., description='id пользователя')
    email: str
    fio: str
    client: bool
    groups: Optional[list[str]] = Field(None, description="Группы пользователя")

