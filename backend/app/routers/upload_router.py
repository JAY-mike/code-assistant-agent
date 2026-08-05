"""文件上传接口"""

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from app.rag.user_upload import UserUploadIndex
from app.models.user import User
from app.auth import get_current_user
from pathlib import Path

router = APIRouter(prefix="/upload", tags=["upload"])

ALLOWED_EXTENSIONS = {".py", ".js", ".md", ".txt"}


@router.post("")
async def upload_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

    content_bytes = await file.read()
    try:
        content = content_bytes.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File must be UTF-8 encoded")

    uploader = UserUploadIndex()
    chunk_count = uploader.add_file(file.filename, content)

    return {
        "filename": file.filename,
        "chunk_count": chunk_count,
        "message": "File indexed successfully",
    }