from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.exc import SQLAlchemyError

from schemas.admin_schemas import Permissions
from database.models.users import Users
from exceptions.database_exc.news import NewsIsEmpty
from schemas.news_schema import NewsModeratedSchema, NewsResponse, NewsCreate, NewsUpdate
from database.logic.news.news import db_news
from utils.auth import get_current_user
from utils.permissions import require_admin_or_permission

router = APIRouter(prefix='/news', tags=['Новости'])


@router.get('/', response_model=NewsResponse, status_code=status.HTTP_200_OK)
async def get_news() -> list[NewsResponse]:
    """
    Получение новостей (Только те что прошли модерацию(в зависимости от конфига))
    """
    try:
        news = db_news.get_news_modeled()
    except NewsIsEmpty as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=e.details,
            headers={"WWW-Authenticate": "Bearer"},
        )

    # response = [
    #     NewsResponse(
    #         **post.__dict__,
    #         like_count=like_count,
    #         comment_count=comment_count
    #     )
    #     for post, like_count, comment_count in news
    # ]
    return NewsResponse.model_validate(news)


@router.post('/create', response_model=NewsResponse, status_code=status.HTTP_201_CREATED)
async def create_news(
        news: NewsCreate,
        user: Users = Depends(require_admin_or_permission(Permissions.CREATE_NEWS))
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


@router.put('/{news_id}', response_model=NewsResponse)
async def update_news(
        news_id: int,
        news_data: NewsUpdate,
        user: Users = Depends(require_admin_or_permission(Permissions.UPDATE_NEWS))
):
    """Обновление поста"""
    try:
        updated_post = await db_news.update_news(news_id, news_data)
        if not updated_post:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Post not found"
            )
        return updated_post
    except SQLAlchemyError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )


@router.delete('/{news_id}')
async def delete_news(
        news_id: int,
        user: Users = Depends(require_admin_or_permission(Permissions.DELETE_NEWS))
):
    """Мягкое удаление поста"""
    try:
        success = await db_news.delete_news(news_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Post not found"
            )
        return {"message": "Post deleted successfully"}
    except SQLAlchemyError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )
    
@router.post('/{news_id}/moderated', status_code=status.HTTP_200_OK)
async def moderated_post(
        news_id: int,
        post_data: NewsModeratedSchema,        
        user: Users = Depends(require_admin_or_permission(Permissions.MODERATED_NEWS))
):
    """Модерация поста"""
    try:
        success = await db_news.moderated_post(news_id, post_data)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Post not found"
            )
        return {"message": "Post moderated successfully"}
    except SQLAlchemyError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )


@router.delete('/hard/{news_id}')
async def hard_delete_news(
        news_id: int,
        user: Users = Depends(require_admin_or_permission(Permissions.DELETE_NEWS))
):
    """Полное удаление поста (только для админов)"""
    try:
        success = await db_news.hard_delete_news(news_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Post not found"
            )
        return {"message": "Post permanently deleted"}
    except SQLAlchemyError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )


@router.get('/{news_id}', response_model=NewsResponse)
async def get_news_by_id(
        news_id: int,
        user: Users = Depends(get_current_user)
) -> NewsResponse:
    """Получение поста по ID"""
    try:
        news = await db_news.get_news_by_id(news_id)
        return news
    except SQLAlchemyError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )


@router.post('/like/{news_id}', status_code=status.HTTP_200_OK)
async def like_unlike_news(
        news_id: int,
        user: Users = Depends(get_current_user)
):
    """Лайк поста"""
    try:
        await db_news.like_unlike_news(news_id, user.id)
        return status.HTTP_200_OK
    except SQLAlchemyError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )