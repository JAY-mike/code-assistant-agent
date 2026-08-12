"""代码检索接口"""

import asyncio
import time
from pathlib import Path
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.rag.dense_retriever import DenseRetriever, SYSTEM_CORPUS
from app.rag.sparse_retriever import SparseRetriever
from app.rag.fusion import rrf, async_hybrid_search
from app.rag.reranker import Reranker
from app.rag.query_rewriter import rewrite
from app.rag.knowledge_bases import (
    DEFAULT_KNOWLEDGE_BASE,
    get_knowledge_base,
)
from app.models.user import User
from app.auth import get_current_user

router = APIRouter(prefix="/search", tags=["search"])

class SearchRequest(BaseModel):
    query: str
    knowledge_base: Literal["tinydb", "project"] = DEFAULT_KNOWLEDGE_BASE
    top_k: int = 5
    use_hybrid: bool = True
    use_hyde: bool = False
    use_rerank: bool = False


class SearchResult(BaseModel):
    text: str
    source: str


class SearchResponse(BaseModel):
    query: str
    knowledge_base: str
    results: list[SearchResult]
    latency_ms: float


class SourceResponse(BaseModel):
    source: str
    content: str


def _resolve_source_file(repo_path: str, source: str) -> Path:
    """Resolve an indexed Python source file without allowing path traversal."""
    project_root = Path(__file__).resolve().parents[3]
    root = Path(repo_path)
    if not root.is_absolute():
        root = project_root / root
    root = root.resolve()

    requested = Path(source)
    if requested.is_absolute() or requested.suffix != ".py":
        raise HTTPException(status_code=400, detail="Invalid source path")

    file_path = (root / requested).resolve()
    try:
        relative_path = file_path.relative_to(root)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid source path") from exc

    excluded = {".git", ".pytest_cache", ".venv", "env", "venv", "__pycache__", "data", "tests"}
    if any(part in excluded for part in relative_path.parts):
        raise HTTPException(status_code=404, detail="Source file not found")
    return file_path


@router.get("/source", response_model=SourceResponse)
async def read_source(
    knowledge_base: Literal["tinydb", "project"],
    source: str,
    current_user: User = Depends(get_current_user),
):
    """Return a public indexed source file for the authenticated caller."""
    knowledge_base_config = get_knowledge_base(knowledge_base)
    file_path = _resolve_source_file(knowledge_base_config.repo_path, source)
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Source file not found")

    try:
        content = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=404, detail="Source file is not UTF-8")
    except OSError as exc:
        raise HTTPException(status_code=404, detail="Source file not found") from exc

    return SourceResponse(source=source, content=content)

@router.post("" , response_model=SearchResponse)
async def search(
    req: SearchRequest,
    current_user: User = Depends(get_current_user),
):
    started_at = time.perf_counter()
    query = req.query.strip()
    if not query:
        raise HTTPException(status_code=400 , detail="Query is empty")

    knowledge_base = get_knowledge_base(req.knowledge_base)
    dense = DenseRetriever(collection_name=knowledge_base.collection_name)
    sparse = SparseRetriever.from_redis(knowledge_base.collection_name)

    if req.use_hyde:
        query = await rewrite(query, strategy="hyde")

    if req.use_hybrid:
        # 复用已有的 async_hybrid_search（含日志打点），默认只搜系统语料
        fused = await async_hybrid_search(
            query, dense, sparse, top_n=req.top_k,
            dense_where=SYSTEM_CORPUS,
        )
    else:
        dense_results = await asyncio.to_thread(
            dense.search, query, req.top_k, SYSTEM_CORPUS
        )
        fused = dense_results

    if req.use_rerank and fused:
        reranker = Reranker()
        fused = await asyncio.to_thread(
            reranker.rerank, query, fused, req.top_k
        )

    return SearchResponse(
        query=req.query,
        knowledge_base=knowledge_base.id,
        results=[
            SearchResult(text=r["text"], source=r["source"])
            for r in fused
        ],
        latency_ms=round((time.perf_counter() - started_at) * 1000, 2),
    )
