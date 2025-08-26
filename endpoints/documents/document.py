from fastapi import APIRouter, Depends, HTTPException, status
from database.logic.documents.document import db_documents
from database.models.users import Users
from exceptions.database_exc.documents_exceptions import DocumentNotFoundException
from schemas.admin_schemas import Permissions
from schemas.documents_schema import DocumentSchemaCreate, DocumentSchemaResponse
from utils.auth import get_current_active_user
from utils.permissions import require_admin_or_permission

router = APIRouter(prefix="/docs", tags=["Документы"])

@router.get('', response_model=list[DocumentSchemaResponse], status_code=status.HTTP_200_OK)
async def get_all_documents(current_user: Users = Depends(get_current_active_user)) -> list[DocumentSchemaResponse] | dict[str, str]:
    try:
        documents = await db_documents.get_all_documents()
    except DocumentNotFoundException:
        return {'message': "documents is empty"}
    return documents


@router.post('/create', response_model=DocumentSchemaResponse, status_code=status.HTTP_201_CREATED)
async def create_document(document: DocumentSchemaCreate,
                          current_user: Users = require_admin_or_permission(Permissions.CREATE_DOCUMENTS)):
    try:
        ...
    except:
        ...
