from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field, model_validator


# Базовые схемы для вложенных моделей без ID
class DocumentFieldBase(BaseModel):
    field_name: str = Field(description='Название поля для клиента')
    field_description: str = Field(description='Описание поля')
    field_example: str = Field(description='Пример того как должно быть заполнено поле')
    service_field: str = Field(description='Название переменной в самом документе')


class DocumentTagsBase(BaseModel):
    tag_name: str = Field(description='Название тега (допустим: от приставов)')


# Схемы для ответа с ID
class DocumentFieldResponse(DocumentFieldBase):
    id: int
    document_id: int

    class Config:
        from_attributes = True


class DocumentTagsResponse(DocumentTagsBase):
    id: int
    document_id: int


# Базовая схема документа без ID
class DocumentBase(BaseModel):
    document_name: str = Field(..., description='Название документа(заголовок)')
    document_description: Optional[str] = Field(description='Описание документа')
    # path: str = Field(..., description='Путь/url до файла')
    instruction: Optional[str] = Field(description='Инструкция для клиента (в каком случае нужен этот документ)')
    price: Optional[float] = Field(description="Цена за доступ к 1 документу")
    sale: bool = Field(default=False, description='Платный ли файл или нет. Если не указано - бесплатен')
    limit_free: Optional[int] = Field(description='Кол-во бесплатных созданий документа в случае, если он платен')

    @model_validator(mode='after')
    def check_price_and_limit(cls, model):
        if model.sale and (model.price is None or model.price <= 0):
            raise ValueError('Платный документ должен иметь положительную цену')
        if model.sale and model.limit_free is not None and model.limit_free < 0:
            raise ValueError('Лимит бесплатных использований не может быть отрицательным')
        return model


# Схема для создания документа (с вложенными объектами без ID)
class DocumentSchemaCreate(DocumentBase):
    fields: List[DocumentFieldBase]
    # tags: List[DocumentTagsBase]


# Схема для ответа (с ID и вложенными объектами с ID)
class DocumentSchemaResponse(DocumentBase):
    id: int
    field: List[DocumentFieldResponse]
    # tags: List[DocumentTagsResponse]

    class Config:
        from_attributes = True


class DocumentGenerateFieldsSchema(BaseModel):
    id: int
    value: str


class DocumentGenerateDocSchema(BaseModel):
    id: int
    fields: list[DocumentGenerateFieldsSchema]


# Дополнительные схемы по необходимости
class DocumentSchemaUpdate(BaseModel):
    document_name: Optional[str] = Field(None, description='Название документа(заголовок)')
    document_description: Optional[str] = Field(None, description='Описание документа')
    path: Optional[str] = Field(None, description='Путь/url до файла')
    instruction: Optional[str] = Field(None, description='Инструкция для клиента')
    price: Optional[float] = Field(None, description="Цена за доступ к 1 документу")
    sale: Optional[bool] = Field(None, description='Платный ли файл')
    limit_free: Optional[int] = Field(None, description='Кол-во бесплатных созданий')