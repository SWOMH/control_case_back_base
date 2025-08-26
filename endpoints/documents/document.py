from fastapi import APIRouter, Depends, HTTPException, status
from database.logic.documents.document import db_documents
from database.models.users import Users
from exceptions.database_exc.documents_exceptions import DocumentNotFoundException
from schemas.documents_schema import DocumentSchemaCreate, DocumentSchemaResponse
from utils.auth import get_current_active_user

router = APIRouter(prefix="/docs", tags=["Документы"])

@router.get('', response_model=list[DocumentSchemaResponse], status_code=status.HTTP_200_OK)
async def get_all_documents(current_user: Users = Depends(get_current_active_user)) -> list[DocumentSchemaResponse] | dict[str, str]:
    try:
        documents = await db_documents.get_all_documents()
    except DocumentNotFoundException:
        return {'message': "documents is empty"}
    return documents


