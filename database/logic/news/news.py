from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy.sql.functions import coalesce
from database.main_connection import DataBaseMainConnect
from database.decorator import connection
from config.constants import DEV_CONSTANT
from sqlalchemy import select, func, exists, or_, case
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from database.models.news_feed import Media, MediaType, Post, Like, Comment
from exceptions.database_exc.news import NewsIsEmptyException
from schemas.news_schema import NewsCreate, NewsModeratedSchema, NewsUpdate
from config.settings import settings


class NewsDataBase(DataBaseMainConnect):

    @connection()
    async def get_news_modeled(self, session: AsyncSession, user_id: int | None = None):
        current_time = datetime.now(timezone.utc)

        likes_subquery = (
            select(
                Like.post_id.label("post_id"),
                func.count(Like.id).label("like_count")
            )
            .group_by(Like.post_id)
            .subquery()
        )

        comments_subquery = (
            select(
                Comment.post_id.label("post_id"),
                func.count(Comment.id).label("comment_count")
            )
            .where(Comment.deleted_at.is_(None))
            .group_by(Comment.post_id)
            .subquery()
        )

        time_condition = or_(Post.time_published.is_(None), Post.time_published <= current_time)

        base_conditions = [
            Post.deleted_at.is_(None),
            Post.published == True,
            time_condition
        ]
        if DEV_CONSTANT.MODIFIED_NEWS:
            base_conditions.append(Post.moderated == True)

        select_cols = [
            Post,
            coalesce(likes_subquery.c.like_count, 0).label("like_count"),
            coalesce(comments_subquery.c.comment_count, 0).label("comment_count"),
        ]

        if user_id is not None:
            liked_exists = exists(
                select(1).where(Like.post_id == Post.id, Like.user_id == user_id)
            ).label("liked_by_user")
            select_cols.append(liked_exists)

        stmt = (
            select(*select_cols)
            .outerjoin(likes_subquery, likes_subquery.c.post_id == Post.id)
            .outerjoin(comments_subquery, comments_subquery.c.post_id == Post.id)
            .where(*base_conditions)
            # подгружаем media чтобы избежать ленивой загрузки после закрытия сессии
            .options(selectinload(Post.media))
            .order_by(Post.time_published.desc().nullslast(), Post.time_created.desc())
        )

        result = await session.execute(stmt)
        rows = result.all()

        if not rows:
            raise NewsIsEmptyException

        return rows

    @connection()
    async def get_news_test(self, session: AsyncSession):
        """Тестовый запрос"""
        stmt = select(Post).where(Post.id == 1)
        result = await session.execute(stmt)
        rows = result.all()
        if not rows:
            raise NewsIsEmptyException
        return result.scalar_one_or_none()

    @connection
    async def create_news(
            self,
            news_data: NewsCreate,
            author_id: int,
            session: AsyncSession,
            image_paths: List[str] | str | None = None,
            video_paths: List[str] | str | None = None            
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
            moderated=False if settings.default_publish_news else True  # По умолчанию пост не модерирован
        )

        session.add(post)
        await session.flush()
        await session.refresh(post)
        
        if image_paths or video_paths:
            if image_paths:
                for image_path in image_paths:
                    image = Media(
                        url=image_path,
                        post_id=post.id,
                        type=MediaType.IMAGE
                    )
                    session.add(image)
            if video_paths:
                for video_path in video_paths:
                    video = Media(
                        url=video_path,
                        post_id=post.id,
                        type=MediaType.VIDEO
                    )
                    session.add(video)
        await session.commit()
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
    
    @connection
    async def moderated_post(self, news_id: int, post_data: NewsModeratedSchema, session: AsyncSession) -> bool:
        """Для модерации поста"""
        post = await self.get_news_by_id(news_id, session)
        if not post:
            return False
        # хз, сработает или нет
        for field, value in post_data.dict(exclude_unset=True).items():
            setattr(post, field, value)
        
        await session.commit()
        await session.refresh(post)
        return True

    @connection
    async def like_unlike_news(
            self,
            news_id: int,
            user_id: int,
            session: AsyncSession
    ) -> bool:
        """Лайк поста"""
        post = await self.get_news_by_id(news_id, session)
        if not post:
            return False

        like = await session.execute(
            select(Like).where(
                Like.post_id == news_id,
                Like.user_id == user_id
            )
        )
        like = like.scalar_one_or_none()
        if like:
            await session.delete(like)
            await session.flush()
            await session.refresh(post)
            return True
        else:
            like = Like(
                post_id=news_id,
                user_id=user_id
            )
            session.add(like)
        await session.flush()
        await session.refresh(post)
        return True



db_news = NewsDataBase()