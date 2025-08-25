from fastapi import APIRouter, status, HTTPException
from sqlalchemy.exc import SQLAlchemyError

from schemas.admin_schemas import Permissions
from database.models.users import Users
from exceptions.database_exc.news import NewsIsEmpty
from schemas.news_schema import NewsResponse, NewsCreate
from database.logic.news.news import db_news
from utils.permissions import require_admin_or_permission

router = APIRouter(prefix='/news', tags=['Новости'])


@router.get(response_model=NewsResponse, status_code=status.HTTP_200_OK)
async def get_news() -> list[NewsResponse]:
    """
    Получение новостей (Только те что прошли модерацию(в зависимости от конфига))
    """
    try:
        news = await db_news.get_news_modeled()
    except NewsIsEmpty as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=e.details,
            headers={"WWW-Authenticate": "Bearer"},
        )

    response = [
        NewsResponse(
            **post.__dict__,
            like_count=like_count,
            comment_count=comment_count
        )
        for post, like_count, comment_count in news
    ]
    return response


@router.post('/create', response_model=NewsResponse, status_code=status.HTTP_201_CREATED)
async def create_news(
        user_id: int,
        news: NewsCreate,
        user: Users = require_admin_or_permission(Permissions.CREATE_NEWS)
):
    try:
        # Создаем пост с author_id из аутентифицированного пользователя
        new_post = await db_news.create_news(
            news_data=news,
            author_id=user.id,  # Берем ID из аутентифицированного пользователя
        )
        return new_post
    except SQLAlchemyError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error creating post: {str(e)}"
        )

