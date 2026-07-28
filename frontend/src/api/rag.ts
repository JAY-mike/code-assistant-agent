import api from './client'

export interface RagSearchReq {
  query: string
  strategy?: 'hybrid' | 'dense' | 'sparse'
  top_k?: number
}

export interface RagSearchResult {
  text: string
  source: string
  chunk_index: number
  score: number | null
}

export interface RagSearchRes {
  results: RagSearchResult[]
  query_rewrite?: string
  latency_ms: number
}

export interface IndexInfo {
  strategy: string
  chunk_size: number
  chunk_overlap: number
  file_count: number
  chunk_count: number
  build_duration_ms: number | null
  created_at: string
}

export function ragSearch(data: RagSearchReq) {
  return api.post<RagSearchRes>('/rag/search', data)
}

export function getIndexInfo() {
  return api.get<IndexInfo[]>('/rag/index-info')
}

export function rebuildIndex() {
  return api.post<{ message: string; chunk_count: number }>('/rag/rebuild')
}
