from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from database.logic.documents.document import db_documents
from database.models.users import Users
from exceptions.database_exc.documents_exceptions import DocumentNotFoundException
from schemas.admin_schemas import Permissions
from schemas.documents_schema import DocumentSchemaCreate, DocumentSchemaResponse
from utils.auth import get_current_active_user
from utils.permissions import require_admin_or_permission
from pathlib import Path
import shutil


router = APIRouter(prefix="/docs", tags=["Документы"])

@router.get('', response_model=list[DocumentSchemaResponse], status_code=status.HTTP_200_OK)
async def get_all_documents(current_user: Users = Depends(get_current_active_user)) -> list[DocumentSchemaResponse] | dict[str, str]:
    try:
        documents = await db_documents.get_all_documents()
    except DocumentNotFoundException:
        return {'message': "documents is empty"}
    return documents


@router.post('/create', response_model=DocumentSchemaResponse, status_code=status.HTTP_201_CREATED)
async def add_document(document: DocumentSchemaCreate,
                       current_user: Users = require_admin_or_permission(Permissions.CREATE_DOCUMENTS),
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
        COMPANY_NAME = 'roga_and_copita'
        date = '27_08_25'
        id = '10'
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
