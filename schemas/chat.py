from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class ChatCreateResponse(BaseModel):
    id: int
    user_id: int
    user_support_id: Optional[int]
    date_created: datetime
    active: bool
    resolved: bool

class MessageCreateRequest(BaseModel):
    message: Optional[str] = Field(None, description="Текст сообщения (может быть пустым при файлах)")

class MessageResponse(BaseModel):
    id: int
    chat_id: int
    sender_id: Optional[int]
    sender_type: str
    message: Optional[str]
    created_at: datetime
    status: str

class ChatDetailResponse(BaseModel):
    id: int
    user_id: int
    user_support_id: Optional[int]
    date_created: datetime
    active: bool
    resolved: bool
    messages: List[MessageResponse] = []