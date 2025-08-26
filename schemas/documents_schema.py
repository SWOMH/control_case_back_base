from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict


class DocumentField(BaseModel):
    field_name: str = Field(description='Название поля для клиента')
    field_description: str = Field(description='Описание поля')
    field_example: str = Field(description='Пример того как должно быть заполнено поле')
    service_field: str = Field(description='Название переменной в самом документе')


class DocumentTags(BaseModel):
    tag_name: str = Field(description='Название тега (допустим: от приставов)')
    document_id: int = Field(description='ID документа')

class DocumentSchema(BaseModel):
    document_name: str = Field(..., description='Название документа(заголовок)')
    document_description: str = Field(..., description='Описание документа')
    path: str = Field(..., description='Путь/url до файла')
    instruction: Optional[str] = Field(description='Иструкция для клиента (в каком случае нужен этот документ)')
    price: Optional[float] = Field(description="Цена за доступ к 1 документу")
    sale: bool = Field(default=False, description='Платный ли файл или нет. Если не указано - бесплатен')
    limit_free: Optional[int] = Field(description='Кол-во бесплатных созданий документа в случаее, если он платен')
    fields: List[DocumentField]
    tags: List[Optional[DocumentTags]]

    @field_validator('price')
    def validate_price(cls, v, values):
        if 'sale' in values and values['sale'] and (v is None or v <= 0):
            raise ValueError('Платный документ должен иметь положительную цену')
        return v

    @field_validator('limit_free')
    def validate_limit_free(cls, v, values):
        if 'sale' in values and values['sale'] and v is not None and v < 0:
            raise ValueError('Лимит бесплатных использований не может быть отрицательным')
        return v
