from fastapi import APIRouter, status, HTTPException
from exceptions.database_exc.news import NewsIsEmpty
from schemas.news_schema import NewsResponse
from database.logic.news.news import db_news

router = APIRouter(prefix='/news', tags=['Новости'])


@router.get('', response_model=NewsResponse, status_code=status.HTTP_201_CREATED)
async def get_news() -> NewsResponse:
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
