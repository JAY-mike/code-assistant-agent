<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h1 class="page-title">RAG 检索</h1>
        <p class="page-desc text-secondary text-sm">混合检索（Dense + Sparse + RRF）测试代码知识库</p>
      </div>
    </div>

    <div class="card search-card">
      <div class="search-row">
        <input
          v-model="query"
          class="input"
          placeholder="输入搜索内容，如：insert document, query method, search algorithm..."
          @keydown.enter="handleSearch"
        />
        <select v-model="strategy" class="input strategy-select">
          <option value="hybrid">混合检索（默认）</option>
          <option value="dense">Dense 语义检索</option>
          <option value="sparse">Sparse 关键词检索</option>
        </select>
        <button class="btn btn-primary" :disabled="loading || !query.trim()" @click="handleSearch">
          <span v-if="loading" class="spinner-sm"></span>
          <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
          搜索
        </button>
      </div>
    </div>

    <!-- Result -->
    <div v-if="result" class="result-area">
      <div class="result-meta card">
        <div class="meta-grid">
          <div class="meta-item">
            <span class="meta-label">检索策略</span>
            <span class="badge badge-primary">{{ strategyText }}</span>
          </div>
          <div class="meta-item">
            <span class="meta-label">结果数</span>
            <span class="meta-value">{{ result.results.length }}</span>
          </div>
          <div class="meta-item">
            <span class="meta-label">延迟</span>
            <span class="meta-value">{{ result.latency_ms }}ms</span>
          </div>
          <div class="meta-item" v-if="result.query_rewrite">
            <span class="meta-label">查询改写（HyDE）</span>
            <span class="meta-value text-sm font-mono">{{ result.query_rewrite }}</span>
          </div>
        </div>
      </div>

      <div class="result-list">
        <div v-for="(item, idx) in result.results" :key="idx" class="result-item card">
          <div class="result-rank">{{ idx + 1 }}</div>
          <div class="result-body">
            <div class="result-source">
              <span class="badge badge-accent font-mono">{{ item.source }}</span>
              <span class="text-xs text-muted">chunk #{{ item.chunk_index }}</span>
              <span v-if="item.score !== null" class="text-xs text-muted">score: {{ item.score.toFixed(4) }}</span>
            </div>
            <pre class="result-code">{{ item.text }}</pre>
          </div>
        </div>
      </div>
    </div>

    <!-- Empty -->
    <div v-else-if="!loading" class="empty-state">
      <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" class="empty-icon"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
      <p class="text-secondary">输入查询内容，测试 RAG 混合检索效果</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { ragSearch, type RagSearchRes } from '@/api/rag'

const query = ref('')
const strategy = ref('hybrid')
const loading = ref(false)
const result = ref<RagSearchRes | null>(null)

const strategyText = ref('混合检索')

async function handleSearch() {
  if (!query.value.trim() || loading.value) return
  loading.value = true
  result.value = null
  try {
    const { data } = await ragSearch({ query: query.value, strategy: strategy.value as any })
    result.value = data
    strategyText.value = strategy.value === 'hybrid' ? '混合检索 (Dense+BM25+RRF)' :
      strategy.value === 'dense' ? 'Dense 语义检索' : 'Sparse BM25 检索'
  } catch (err: any) {
    console.error(err)
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.page { padding: 24px; max-width: 960px; margin: 0 auto; }
.page-header { margin-bottom: 24px; }
.page-title { font-size: 1.4rem; font-weight: 700; letter-spacing: -0.02em; margin-bottom: 4px; }
.page-desc { margin: 0; }

.search-card { margin-bottom: 20px; }
.search-row { display: flex; gap: 10px; }
.search-row .input { flex: 1; }
.strategy-select { max-width: 200px; cursor: pointer; }
.spinner-sm {
  width: 16px; height: 16px;
  border: 2px solid rgba(255,255,255,0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
  display: inline-block;
}
@keyframes spin { to { transform: rotate(360deg); } }

.result-area { display: flex; flex-direction: column; gap: 16px; }
.result-meta { padding: 16px 20px; }
.meta-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; }
.meta-item { display: flex; flex-direction: column; gap: 4px; }
.meta-label { font-size: 0.75rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.04em; font-weight: 600; }
.meta-value { font-size: 0.95rem; font-weight: 500; }

.result-list { display: flex; flex-direction: column; gap: 12px; }
.result-item { display: flex; gap: 16px; padding: 16px; }
.result-rank {
  width: 28px; height: 28px;
  border-radius: 50%;
  background: var(--primary-subtle);
  color: var(--primary-hover);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.8rem;
  font-weight: 700;
  flex-shrink: 0;
}
.result-body { flex: 1; min-width: 0; }
.result-source { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; flex-wrap: wrap; }
.result-code {
  font-family: var(--font-mono);
  font-size: 0.8rem;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 200px;
  overflow-y: auto;
  background: var(--bg-primary);
  padding: 12px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border);
}

.empty-state { display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 80px 20px; gap: 12px; }
.empty-icon { color: var(--text-muted); }
</style>
