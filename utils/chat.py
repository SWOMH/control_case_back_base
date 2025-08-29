import aiofiles
from pathlib import Path
import uuid

UPLOAD_DIR = Path("uploads/chat_attachments")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

async def save_upload_file(upload_file) -> dict:
    """
    Сохраняет UploadFile на диск (можно заменить на S3).
    Возвращает метаданные.
    """
    ext = Path(upload_file.filename).suffix
    uid = uuid.uuid4().hex
    filename = f"{uid}{ext}"
    dest = UPLOAD_DIR / filename

    async with aiofiles.open(dest, "wb") as f:
        content = await upload_file.read()  # осторожно с большими файлами
        await f.write(content)

    return {
        "filename": upload_file.filename,
        "file_path": str(dest),
        "content_type": upload_file.content_type,
        "size": len(content),
    }