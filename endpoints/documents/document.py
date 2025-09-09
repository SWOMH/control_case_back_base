import datetime
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from config.constants import DEV_CONSTANT
from database.logic.documents.document import db_documents
from database.models.users import Users
from exceptions.database_exc.documents_exceptions import DocumentNotFoundException
from schemas.admin_schemas import Permissions
from schemas.documents_schema import DocumentSchemaCreate, DocumentSchemaResponse, DocumentGenerateDocSchema
from utils.auth import get_current_active_user
from utils.permissions import require_admin_or_permission
from pathlib import Path
import shutil
from docxtpl import DocxTemplate
import uuid
from docx2pdf import convert


router = APIRouter(prefix="/docs", tags=["Документы"])

@router.get('', response_model=list[DocumentSchemaResponse], status_code=status.HTTP_200_OK)
async def get_all_documents(current_user: Users = Depends(get_current_active_user)) -> list[DocumentSchemaResponse] | dict[str, str]:
    try:
        documents = await db_documents.get_all_documents()
    except DocumentNotFoundException:
        return {'message': "documents is empty"}
    return documents


@router.get('/{document_id}', tags=["Документы"])
async def get_document_by_id(document_id: int,
                             current_user: Users = Depends(get_current_active_user)) -> DocumentSchemaResponse:
    try:
        document = await db_documents.get_document_by_id(document_id)
        return document
    except:
        ...


@router.post('/generate', tags=['Документы'])
async def generate_document(document: DocumentGenerateDocSchema,
                            user: Users = Depends(get_current_active_user)):
    db_doc = await db_documents.get_document_by_id(document.id)
    if not db_doc:
        raise HTTPException(status_code=404, detail="Документ не найден")
    can_generate = await db_documents.check_user_can_generate(user, db_doc.price)
    if not can_generate:
        raise HTTPException(status_code=423, detail="Insufficient funds")
    template_path = Path(db_doc.path)
    if not template_path.exists():
        raise HTTPException(status_code=404, detail="Шаблон не найден на сервере")

    # словарь для замены
    context = {}
    for field in document.fields:
        # Находим описание поля из базы
        field_meta = next((f for f in db_doc.fields if f.id == field.id), None)
        if not field_meta:
            raise HTTPException(status_code=400, detail=f"Поле с id={field.id} не найдено")
        context[field_meta.service_field] = field.value

    # Подставляем значения в docx
    tpl = DocxTemplate(str(template_path))
    tpl.render(context)

    # Генерируем уникальное имя
    output_dir = Path("generated_docs")
    output_dir.mkdir(parents=True, exist_ok=True)

    unique_name = f"doc_{uuid.uuid4().hex}.docx"
    output_path = output_dir / unique_name

    tpl.save(output_path)

    await db_documents.generate_document_created(
        document_id=document.id,
        user_id=user.id,
    )

    # Возвращаем путь (пока так, потом мб переделаю)
    return {"url": f"/static/generated_docs/{unique_name}"}


@router.post('/generate-pdf', tags=['Документы'])
async def generate_pdf(document: DocumentGenerateDocSchema,
                       user: Users = Depends(get_current_active_user)):
    # Сначала делаем DOCX (как выше)
    result = await generate_document(document, user)
    docx_path = Path("static") / result["url"].lstrip("/")

    pdf_name = docx_path.stem + ".pdf"
    pdf_path = docx_path.parent / pdf_name

    convert(docx_path, pdf_path)
    return {"url": f"/static/generated_docs/{pdf_name}"}


@router.post('/create', response_model=DocumentSchemaResponse, status_code=status.HTTP_201_CREATED)
async def add_document(document: DocumentSchemaCreate,
                       current_user: Users = Depends(require_admin_or_permission(Permissions.CREATE_DOCUMENTS)),
                       file: UploadFile = File(...)):
    try:
        # Проверяем тип файла
        allowed_extensions = {'.docx', '.xlsx', '.doc', '.xls'}
        file_extension = Path(file.filename).suffix.lower()

        if file_extension not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail="Недопустимый формат файла. Разрешены: .docx, .xlsx, .doc, .xls"
            )

        # TODO: Не знаю как сейвить либо "{Название_компании}{id_на_s3}.docx" или как-то иначе
        # unique_filename = f"{uuid.uuid4()}{file_extension}"
        COMPANY_NAME = DEV_CONSTANT.company_name
        date = datetime.now().strftime("%d_%m_%Y")
        id = uuid.uuid4()
        unique_filename = f"{COMPANY_NAME}__{date}__{id}{file_extension}"

        upload_dir = Path("uploads/documents")
        upload_dir.mkdir(parents=True, exist_ok=True)

        file_path = upload_dir / unique_filename

        # Сохраняем файл
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)


        # Здесь код для сохранения в базу данных
        # document = await Document.create(document, document_path)

        return document
    except:
        ...
