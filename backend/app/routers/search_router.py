"""代码检索接口"""

import asyncio
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.rag.dense_retriever import DenseRetriever, SYSTEM_CORPUS
from app.rag.sparse_retriever import SparseRetriever
from app.rag.fusion import rrf, async_hybrid_search
from app.rag.reranker import Reranker
from app.rag.query_rewriter import rewrite
from app.models.user import User
from app.auth import get_current_user

router = APIRouter(prefix="/search", tags=["search"])

class SearchRequest(BaseModel):
    query: str
    top_k: int = 5
    use_hybrid: bool = True
    use_hyde: bool = False
    use_rerank: bool = False


class SearchResult(BaseModel):
    text: str
    source: str


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]
    latency_ms: float

@router.post("" , response_model=SearchResponse)
async def search(
    req: SearchRequest,
    current_user: User = Depends(get_current_user),
):
    query = req.query.strip()
    if not query:
        raise HTTPException(status_code=400 , detail="Query is empty")

    dense = DenseRetriever()
    sparse = SparseRetriever.from_redis()

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
        results=[
            SearchResult(text=r["text"], source=r["source"])
            for r in fused
        ],
        latency_ms=0.0,  # 简化：不测延迟，需要的话再补
    )