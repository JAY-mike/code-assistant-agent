<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h1 class="page-title">索引管理</h1>
        <p class="page-desc text-secondary text-sm">查看索引构建历史，手动触发重建</p>
      </div>
      <button class="btn btn-primary" :disabled="rebuilding" @click="handleRebuild">
        <span v-if="rebuilding" class="spinner-sm"></span>
        <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>
        重建索引
      </button>
    </div>

    <div v-if="rebuilding" class="card rebuild-status">
      <div class="rebuild-progress">
        <div class="spinner"></div>
        <span>正在重建索引，请稍候...</span>
      </div>
    </div>

    <div v-if="rebuildMsg" class="card rebuild-msg">
      <span class="badge badge-success">成功</span>
      {{ rebuildMsg }}
    </div>

    <!-- Index version list -->
    <div class="table-card card">
      <table class="table">
        <thead>
          <tr>
            <th>ID</th>
            <th>策略</th>
            <th>块大小</th>
            <th>重叠</th>
            <th>文件数</th>
            <th>块数</th>
            <th>耗时</th>
            <th>创建时间</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="v in versions" :key="v.created_at">
            <td class="font-mono text-xs text-muted">-</td>
            <td><span class="badge badge-primary">{{ v.strategy }}</span></td>
            <td>{{ v.chunk_size }}</td>
            <td>{{ v.chunk_overlap }}</td>
            <td>{{ v.file_count }}</td>
            <td><strong>{{ v.chunk_count }}</strong></td>
            <td class="font-mono text-sm">{{ v.build_duration_ms !== null ? v.build_duration_ms + 'ms' : '-' }}</td>
            <td class="text-sm text-secondary">{{ formatTime(v.created_at) }}</td>
          </tr>
          <tr v-if="versions.length === 0">
            <td colspan="8" class="table-empty text-secondary">暂无索引记录</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { getIndexInfo, rebuildIndex, type IndexInfo } from '@/api/rag'

const versions = ref<IndexInfo[]>([])
const rebuilding = ref(false)
const rebuildMsg = ref('')

onMounted(loadVersions)

async function loadVersions() {
  try {
    const { data } = await getIndexInfo()
    versions.value = data
  } catch (err) {
    console.error(err)
  }
}

async function handleRebuild() {
  rebuilding.value = true
  rebuildMsg.value = ''
  try {
    const { data } = await rebuildIndex()
    rebuildMsg.value = `索引重建完成，共 ${data.chunk_count} 个块`
    await loadVersions()
  } catch (err: any) {
    rebuildMsg.value = '重建失败：' + (err.response?.data?.detail || err.message)
  } finally {
    rebuilding.value = false
  }
}

function formatTime(ts: string) {
  return new Date(ts).toLocaleString('zh-CN')
}
</script>

<style scoped>
.page { padding: 24px; max-width: 960px; margin: 0 auto; }
.page-header { display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 24px; gap: 16px; }
.page-title { font-size: 1.4rem; font-weight: 700; letter-spacing: -0.02em; margin-bottom: 4px; }
.page-desc { margin: 0; }

.rebuild-status { margin-bottom: 16px; }
.rebuild-progress { display: flex; align-items: center; gap: 12px; color: var(--text-secondary); }
.rebuild-msg { display: flex; align-items: center; gap: 12px; margin-bottom: 16px; }

.spinner {
  width: 20px; height: 20px;
  border: 2px solid var(--border);
  border-top-color: var(--primary);
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}
.spinner-sm {
  width: 16px; height: 16px;
  border: 2px solid rgba(255,255,255,0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
  display: inline-block;
}
@keyframes spin { to { transform: rotate(360deg); } }

.table-card { padding: 0; overflow-x: auto; }
.table { width: 100%; border-collapse: collapse; }
.table th {
  padding: 12px 16px;
  text-align: left;
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--text-muted);
  border-bottom: 1px solid var(--border);
  white-space: nowrap;
}
.table td {
  padding: 12px 16px;
  font-size: 0.9rem;
  border-bottom: 1px solid var(--border);
}
.table tr:last-child td { border-bottom: none; }
.table tr:hover td { background: rgba(255,255,255,0.02); }
.table-empty { text-align: center; padding: 32px 16px !important; }
</style>
