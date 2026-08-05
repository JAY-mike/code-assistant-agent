"""文件上传接口"""

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from pydantic import BaseModel
from app.rag.user_upload import UserUploadIndex
from app.models.user import User
from app.auth import get_current_user
from pathlib import Path

router = APIRouter(prefix="/upload", tags=["upload"])

ALLOWED_EXTENSIONS = {".py", ".js", ".md", ".txt"}


class UploadSearchRequest(BaseModel):
    query: str
    top_k: int = 5


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
    chunk_count = uploader.add_file(file.filename, content, owner_id=current_user.id)

    return {
        "filename": file.filename,
        "chunk_count": chunk_count,
        "message": "File indexed successfully",
    }


@router.post("/search")
async def search_upload(
    req: UploadSearchRequest,
    current_user: User = Depends(get_current_user),
):
    """只检索当前用户自己上传的内容（owner_id 隔离）"""
    query = req.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query is empty")

    uploader = UserUploadIndex()
    results = uploader.search(query, owner_id=current_user.id, k=req.top_k)

    return {
        "query": req.query,
        "results": [
            {"text": r["text"], "source": r["source"]}
            for r in results
        ],
    }