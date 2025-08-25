from datetime import datetime, timezone
from sqlalchemy.sql.functions import coalesce
from database.main_connection import DataBaseMainConnect
from database.decorator import connection
from config.constants import DEV_CONSTANT
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from database.models.news_feed import Post, Like, Comment



class NewsDataBase(DataBaseMainConnect):

    @connection
    async def get_news_modeled(self, session: AsyncSession):
        """
        Получение новостей которые уже промоделировали и готовы к публекации
        """
        current_time = datetime.now(timezone.utc)  # Для сравнения с timezone-aware датами

        # Подзапросы для агрегации лайков и комментариев
        likes_subquery = (
            select(
                Like.post_id,
                func.count(Like.id).label('like_count')
            )
            .group_by(Like.post_id)
            .subquery()
        )

        comments_subquery = (
            select(
                Comment.post_id,
                func.count(Comment.id).label('comment_count')
            )
            .where(Comment.deleted_at.is_(None))  # Исключаем удалённые комментарии
            .group_by(Comment.post_id)
            .subquery()
        )

        # Основной запрос с объединением данных
        if DEV_CONSTANT.MODIFIED_NEWS:
            stmt = (
                select(
                    Post,
                    coalesce(likes_subquery.c.like_count, 0).label('like_count'),
                    coalesce(comments_subquery.c.comment_count, 0).label('comment_count')
                )
                .outerjoin(likes_subquery, likes_subquery.c.post_id == Post.id)
                .outerjoin(comments_subquery, comments_subquery.c.post_id == Post.id)
                .where(
                    Post.moderated == True,
                    Post.time_published >= current_time,
                    Post.published == True
                )
            )
        else:
            stmt = (
                select(
                    Post,
                    coalesce(likes_subquery.c.like_count, 0).label('like_count'),
                    coalesce(comments_subquery.c.comment_count, 0).label('comment_count')
                )
                .outerjoin(likes_subquery, likes_subquery.c.post_id == Post.id)
                .outerjoin(comments_subquery, comments_subquery.c.post_id == Post.id)
                .where(
                    Post.time_published >= current_time,
                    Post.published == True
                )
            )

        result = await session.execute(stmt)
        if len(result) == 0:
            raise NewsIsEmpty
        return result.all()




db_news = NewsDataBase()