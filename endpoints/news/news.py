import datetime
import shutil
import uuid
from fastapi import APIRouter, Depends, Form, status, HTTPException, UploadFile, File, Request
from starlette.datastructures import FormData
from config.constants import DEV_CONSTANT
from database.models.news_feed import MediaType
from sqlalchemy.exc import SQLAlchemyError
from typing import List, Optional
from pathlib import Path
from schemas.admin_schemas import Permissions
from database.models.users import Users
from exceptions.database_exc.news import NewsIsEmptyException
from schemas.news_schema import NewsModeratedSchema, NewsResponse, NewsCreate, NewsUpdate
from database.logic.news.news import db_news
from utils.auth import get_current_user, get_current_user_optional
from utils.permissions import require_admin_or_permission

router = APIRouter(prefix='/news', tags=['Новости'])


@router.get('', response_model=list[NewsResponse], status_code=status.HTTP_200_OK)
async def get_news(user: Optional[Users] = Depends(get_current_user_optional)) -> list[NewsResponse]:
    # TODO: Разобраться с лайками. Постоянно true приходит
    try:
        user_id = user.id if user else None
        rows = await db_news.get_news_modeled(user_id=user_id)
    except NewsIsEmptyException:
        return []  # или 204, по вкусу

    response: list[NewsResponse] = []

    for row in rows:
        # если user_id есть, row: (Post, like_count, comment_count, liked_by_user)
        # иначе: (Post, like_count, comment_count)
        if user_id is not None:
            post, like_count, comment_count, liked_by_user = row
        else:
            post, like_count, comment_count = row
            liked_by_user = None

        # формируем списки медиа: фильтруем deleted==False
        image_urls: list[str] = []
        video_urls: list[str] = []

        # post.media уже загружен благодаря selectinload
        for m in getattr(post, "media", []) or []:
            if getattr(m, "deleted", False):
                continue
            # m.type — экземпляр Enum (MediaType). Сравниваем по значению или Enum
            if m.type == MediaType.IMAGE or str(m.type).lower() == "image":
                image_urls.append(str(m.url))
            elif m.type == MediaType.VIDEO or str(m.type).lower() == "video":
                video_urls.append(str(m.url))

        # собираем словарь явно (не используем post.__dict__)
        resp = NewsResponse(
            id=post.id,
            time_created=post.time_created,
            title=post.title,
            content=post.content,
            image_url=image_urls,
            video_url=video_urls,
            comment_count=int(comment_count or 0),
            like_count=int(like_count or 0),
            liked_by_user=bool(liked_by_user) if liked_by_user is not None else None
        )
        response.append(resp)

    return response


@router.get('/unauth', response_model=list[NewsResponse], status_code=status.HTTP_200_OK)
async def get_news() -> list[NewsResponse]:
    try:        
        rows = await db_news.get_news_modeled()
    except NewsIsEmptyException:
        return []  # или 204, по вкусу

    response: list[NewsResponse] = []

    for row in rows:
        
        post, like_count, comment_count = row
        liked_by_user = None

        # формируем списки медиа: фильтруем deleted==False
        image_urls: list[str] = []
        video_urls: list[str] = []

        # post.media уже загружен благодаря selectinload
        for m in getattr(post, "media", []) or []:
            if getattr(m, "deleted", False):
                continue
            # m.type — экземпляр Enum (MediaType). Сравниваем по значению или Enum
            if m.type == MediaType.IMAGE or str(m.type).lower() == "image":
                image_urls.append(str(m.url))
            elif m.type == MediaType.VIDEO or str(m.type).lower() == "video":
                video_urls.append(str(m.url))

        # собираем словарь явно (не используем post.__dict__)
        resp = NewsResponse(
            id=post.id,
            time_created=post.time_created,
            title=post.title,
            content=post.content,
            image_url=image_urls,
            video_url=video_urls,
            comment_count=int(comment_count or 0),
            like_count=int(like_count or 0),
            liked_by_user=bool(liked_by_user) if liked_by_user is not None else None
        )
        response.append(resp)

    return response

@router.post('/create', response_model=NewsResponse, status_code=status.HTTP_201_CREATED)
async def create_news(
    request: Request,
    user: Users = Depends(require_admin_or_permission(Permissions.CREATE_NEWS))
):
    """
    Обработчик, который поддерживает и application/json, и multipart/form-data.
    curl -X POST "http://HOST/create" \
        -H "Authorization: Bearer <token>" \
        -F 'news={"title":"TITLE SOSI","content":"CONTENT SOSY"}' \
        -F "files=@/path/to/image.jpg" \
        -F "files=@/path/to/video.mp4"

    Ну или если без файлов:
    curl -X POST "http://HOST/create" \
        -H "Authorization: Bearer <token>" \
        -F 'news={"title":"TITLE SOSI","content":"CONTENT SOSY"}'
    """
    content_type = request.headers.get("content-type", "")
    image_urls: List[str] = []
    video_urls: List[str] = []

    # --- Branch: multipart/form-data (обычно из /docs при загрузке файлов) ---
    if "multipart/form-data" in content_type:
        form: FormData = await request.form()  # starlette FormData
        # news может быть текстом JSON в поле 'news'
        news_field = form.get("news")
        # извлекаем все значения files (если есть) — FormData поддерживает getlist
        try:
            files = form.getlist("files")
        except Exception:
            files = []

        # фильтруем: берем только UploadFile с непустым filename
        filtered_files = []
        for f in files:
            # в swagger пустой файл иногда приходит как "" (str) или UploadFile с empty filename
            if isinstance(f, UploadFile) and getattr(f, "filename", None):
                filtered_files.append(f)

        # сохраняем файлы (если есть)
        if filtered_files:
            COMPANY_NAME = DEV_CONSTANT.company_name
            date = datetime.datetime.now(datetime.timezone.utc).strftime("%d_%m_%Y")
            upload_dir = Path("uploads/media")
            upload_dir.mkdir(parents=True, exist_ok=True)

            image_exts = {'.png', '.jpg', '.jpeg', '.gif', '.webp'}
            video_exts = {'.mkv', '.mp4'}
            allowed_extensions = image_exts | video_exts

            for file in filtered_files:
                ext = Path(file.filename).suffix.lower()
                if ext not in allowed_extensions:
                    raise HTTPException(status_code=400, detail="Недопустимый формат файла.")
                unique_filename = f"{COMPANY_NAME}__{date}__{uuid.uuid4()}{ext}"
                file_path = upload_dir / unique_filename
                with open(file_path, "wb") as buffer:
                    shutil.copyfileobj(file.file, buffer)
                if ext in image_exts:
                    image_urls.append(str(file_path))
                else:
                    video_urls.append(str(file_path))

        # news_field может быть JSON-строкой
        if isinstance(news_field, str):
            news_data = NewsCreate.model_validate_json(news_field)
        else:
            # если поле отсутствует или не строка — бросаем ошибку
            raise HTTPException(status_code=400, detail="Поле 'news' обязательно и должно содержать JSON-строку.")

    # --- Branch: application/json (например, обычный POST из /docs как raw JSON) ---
    elif "application/json" in content_type or content_type == "":
        # content_type == "" может быть в некоторых конфигурациях, поэтому пробуем parse json
        try:
            body = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="Невозможно распарсить JSON тело запроса.")
        # в JSON ожидаем структуру, соответствующую NewsCreate
        news_data = NewsCreate.model_validate(body)  # pydantic v2
        # files отсутствуют — всё ок

    else:
        # неизвестный content-type
        raise HTTPException(status_code=415, detail=f"Unsupported content-type: {content_type}")

    # --- Создаём запись в БД ---
    try:
        if image_urls or video_urls:
            new_post = await db_news.create_news(
                news_data=news_data,
                author_id=user.id,
                image_paths=image_urls or None,
                video_paths=video_urls or None
            )
        else:
            new_post = await db_news.create_news(
                news_data=news_data,
                author_id=user.id
            )
        return new_post

    except SQLAlchemyError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Database error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Error creating post: {str(e)}")


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