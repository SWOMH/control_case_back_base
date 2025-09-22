from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import selectinload

from database.main_connection import DataBaseMainConnect
from database.decorator import connection
from database.models.documents import DocumentsUser
from database.models.documents_app import DocumentsApp, DocumentCreated, DocumentFields, \
    PurchasedDocuments
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.users import Users
from exceptions.database_exc.documents_exceptions import DocumentAlreadyExistsException, DocumentNotFoundException, \
    InsufficientFundsForGenerateDocument
from schemas.documents_schema import DocumentSchemaCreate, DocumentSchemaResponse
from sqlalchemy import select, and_
from datetime import date


class DocumentDataBase(DataBaseMainConnect):

    @connection()
    async def create_document(self, document: DocumentSchemaCreate, session: AsyncSession):
        try:
            # 1. Проверка существования документа с таким же именем
            stmt = select(DocumentsApp).where(
                and_(
                    DocumentsApp.document_name == document.document_name,
                    DocumentsApp.activity == True
                )
            )
            result = await session.execute(stmt)
            existing_document = result.scalar_one_or_none()

            if existing_document:
                raise DocumentAlreadyExistsException(
                    f"Документ с именем '{document.document_name}' уже существует"
                )

            # 2. Проверка корректности цены и лимита
            if document.sale and (document.price is None or document.price <= 0):
                raise ValueError("Платный документ должен иметь положительную цену")

            if document.sale and document.limit_free is not None and document.limit_free < 0:
                raise ValueError("Лимит бесплатных использований не может быть отрицательным")

            # 3. Создание документа
            new_document = DocumentsApp(
                document_name=document.document_name,
                document_description=document.document_description,
                path=document.path,
                instruction=document.instruction,
                price=document.price,
                sale=document.sale,
                limit_free=document.limit_free
            )

            session.add(new_document)
            await session.flush()  # Асинхронный flush

            # 4. Добавление полей документа
            if hasattr(document, 'fields') and document.fields:
                for field in document.fields:
                    # Проверка обязательных полей
                    if not field.field_name:
                        raise ValueError("Название поля не может быть пустым")

                    field_doc = DocumentFields(
                        document_id=new_document.id,
                        field_name=field.field_name,
                        field_description=field.field_description,
                        field_example=field.field_example,
                        service_field=field.service_field,
                    )
                    session.add(field_doc)

                await session.flush()

            # # 5. Добавление тегов (если есть)
            # if hasattr(document, 'tags') and document.tags:
            #     for tag_name in document.tags:
            #         # Проверяем существование тега
            #         tag_stmt = select(DocumentTags).where(
            #             DocumentTags.tag_name == tag_name
            #         )
            #         tag_result = await session.execute(tag_stmt)
            #         existing_tag = tag_result.scalar_one_or_none()
            #
            #         if existing_tag:
            #             # Связываем существующий тег
            #             association = DocumentTagAssociation(
            #                 document_id=new_document.id,
            #                 tag_id=existing_tag.id
            #             )
            #         else:
            #             # Создаем новый тег
            #             new_tag = DocumentTags(tag_name=tag_name)
            #             session.add(new_tag)
            #             await session.flush()
            #
            #             association = DocumentTagAssociation(
            #                 document_id=new_document.id,
            #                 tag_id=new_tag.id
            #             )
            #
            #         session.add(association)

                await session.flush()

            # 6. Фиксируем изменения
            await session.commit()

            # 7. Возвращаем созданный документ с полями
            return await self.get_document_by_id(new_document.id, session)

        except SQLAlchemyError as e:
            await session.rollback()
            raise Exception(f"Ошибка при создании документа: {str(e)}")
        except Exception as e:
            await session.rollback()
            raise e


    @connection()
    async def check_user_can_generate(self, user: Users, document_price: float) -> bool:
        """Проверяет возможность создания документа (если документ платный)"""

        if user.is_admin:
            return True  # Тоже пока заглушка для тестов
        # TODO: Тут должен быть метод получения баланса пользователя, а пока заглушка будет
        return False if user.balance < document_price else True


    @connection()
    async def generate_document_created(self, document_id: int, user_id: int, session: AsyncSession):
        """Просто записывает какой человек создал документ и когда"""
        generate_doc = DocumentCreated(
            document_id=document_id,
            user_id=user_id,
            created=True,
            date=date.today()
        )
        session.add(generate_doc)
        session.commit()


    @connection()
    async def get_document_by_id(self, document_id: int, session: AsyncSession) -> DocumentSchemaResponse:
        """Получение документа по ID со всеми связанными данными"""
        stmt = select(DocumentsApp).where(
            and_(
                DocumentsApp.id == document_id,
                DocumentsApp.activity == True
            )
        ).options(
            selectinload(DocumentsApp.field)
            # selectinload(DocumentsApp.tags).selectinload(DocumentTagAssociation.tag)
        )

        result = await session.execute(stmt)
        document = result.scalar_one_or_none()

        if not document:
            raise DocumentNotFoundException

        return document


    @connection()
    async def get_all_documents(self, session: AsyncSession, skip: int = 0, limit: int = 100):
        """Получение всех документов с пагинацией"""
        stmt = select(DocumentsApp).where(
            DocumentsApp.activity == True
        ).options(
            selectinload(DocumentsApp.field)
            # selectinload(DocumentsApp.tags).selectinload(DocumentTagAssociation.tag)
        ).offset(skip).limit(limit)

        result = await session.execute(stmt)
        documents = result.scalars().all()
        if not documents:
            raise DocumentNotFoundException
        # return documents
        return [DocumentSchemaResponse.model_validate(d) for d in documents]


    @connection()
    async def update_document(self, document_id: int, update_data: dict, session: AsyncSession):
        """Обновление документа"""
        document = await self.get_document_by_id(document_id, session)

        # Проверяем, не пытаемся ли изменить имя на уже существующее
        if 'document_name' in update_data and update_data['document_name'] != document.document_name:
            stmt = select(DocumentsApp).where(
                and_(
                    DocumentsApp.document_name == update_data['document_name'],
                    DocumentsApp.activity == True,
                    DocumentsApp.id != document_id
                )
            )
            result = await session.execute(stmt)
            existing_document = result.scalar_one_or_none()

            if existing_document:
                raise DocumentAlreadyExistsException(
                    f"Документ с именем '{update_data['document_name']}' уже существует"
                )

        # Обновляем поля
        for field, value in update_data.items():
            if hasattr(document, field):
                setattr(document, field, value)

        await session.commit()
        return document


    @connection()
    async def delete_document(self, document_id: int, session: AsyncSession):
        """Мягкое удаление документа (установка activity = False)"""
        document = await self.get_document_by_id(document_id, session)
        document.activity = False
        await session.commit()


db_documents = DocumentDataBase()
