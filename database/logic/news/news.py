from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.sql.functions import coalesce
from database.main_connection import DataBaseMainConnect
from database.decorator import connection
from config.constants import DEV_CONSTANT
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from database.models.news_feed import Post, Like, Comment
from exceptions.database_exc.news import NewsIsEmpty
from schemas.news_schema import NewsCreate, NewsUpdate


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

    @connection
    async def create_news(
            self,
            news_data: NewsCreate,
            author_id: int,
            session: AsyncSession
    ) -> Post:
        # Подготавливаем данные для создания
        post_dict = news_data.dict(exclude_unset=True)

        # Устанавливаем время публикации если published=True
        if post_dict.get('published') and not post_dict.get('time_published'):
            post_dict['time_published'] = datetime.now(timezone.utc)

        # Создаем объект поста
        post = Post(
            **post_dict,
            author_id=author_id,  # Используем author_id из параметра
            moderated=False  # По умолчанию пост не модерирован
        )

        session.add(post)
        await session.flush()
        await session.refresh(post)
        return post

    @connection
    async def get_news_by_id(
            self,
            news_id: int,
            session: AsyncSession
    ) -> Optional[Post]:
        """Получить пост по ID"""
        result = await session.execute(
            select(Post).where(
                Post.id == news_id,
                Post.deleted_at.is_(None)  # Исключаем удаленные посты
            )
        )
        return result.scalar_one_or_none()

    @connection
    async def update_news(
            self,
            news_id: int,
            news_data: NewsUpdate,
            session: AsyncSession
    ) -> Optional[Post]:
        """Обновить пост"""
        # Получаем пост
        post = await self.get_news_by_id(news_id, session)
        if not post:
            return None

        # Подготавливаем данные для обновления
        update_data = news_data.dict(exclude_unset=True)

        # Если меняем статус published, обновляем time_published
        if 'published' in update_data:
            if update_data['published'] and not post.time_published:
                update_data['time_published'] = datetime.now(timezone.utc)
            elif not update_data['published']:
                update_data['time_published'] = None

        # Обновляем поля
        for field, value in update_data.items():
            setattr(post, field, value)

        # Время обновления проставится автоматически благодаря onupdate
        await session.commit()
        await session.refresh(post)
        return post

    @connection
    async def delete_news(
            self,
            news_id: int,
            session: AsyncSession
    ) -> bool:
        """Мягкое удаление поста (устанавливаем deleted_at)"""
        post = await self.get_news_by_id(news_id, session)
        if not post:
            return False

        post.deleted_at = datetime.now(timezone.utc)
        await session.commit()
        return True

    @connection
    async def hard_delete_news(
            self,
            news_id: int,
            session: AsyncSession
    ) -> bool:
        """Полное удаление поста из базы"""
        post = await self.get_news_by_id(news_id, session)
        if not post:
            return False

        await session.delete(post)
        await session.commit()
        return True



db_news = NewsDataBase()