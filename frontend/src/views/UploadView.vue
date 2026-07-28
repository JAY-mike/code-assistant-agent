<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h1 class="page-title">文件上传</h1>
        <p class="page-desc text-secondary text-sm">上传代码文件（.py / .js / .java / .md），自动索引到独立知识库</p>
      </div>
    </div>

    <!-- Upload zone -->
    <div
      class="upload-zone card"
      :class="{ 'upload-zone--active': dragging }"
      @dragover.prevent="dragging = true"
      @dragleave.prevent="dragging = false"
      @drop.prevent="handleDrop"
    >
      <div class="upload-icon">
        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
          <polyline points="17 8 12 3 7 8"/>
          <line x1="12" y1="3" x2="12" y2="15"/>
        </svg>
      </div>
      <p class="upload-text">拖拽文件到此处，或点击选择文件</p>
      <p class="upload-hint text-xs text-muted">支持 .py .js .java .md .txt .pdf 格式</p>
      <label class="btn btn-primary upload-btn">
        选择文件
        <input type="file" multiple accept=".py,.js,.java,.md,.txt,.pdf" @change="handleFileSelect" hidden />
      </label>
    </div>

    <!-- Upload queue -->
    <div v-if="uploadQueue.length > 0" class="upload-queue">
      <div v-for="(item, idx) in uploadQueue" :key="idx" class="card queue-item">
        <div class="queue-info">
          <span class="queue-name font-mono text-sm">{{ item.file.name }}</span>
          <span class="text-xs text-muted">{{ (item.file.size / 1024).toFixed(1) }} KB</span>
        </div>
        <div v-if="item.status === 'uploading'" class="queue-status">
          <div class="spinner-sm"></div>
          <span class="text-xs text-secondary">上传中...</span>
        </div>
        <div v-else-if="item.status === 'done'" class="queue-status">
          <span class="badge badge-success">成功</span>
          <span class="text-xs text-muted">{{ item.result?.chunk_count || 0 }} 块</span>
        </div>
        <div v-else-if="item.status === 'error'" class="queue-status">
          <span class="badge badge-error">失败</span>
          <span class="text-xs text-error">{{ item.error }}</span>
        </div>
      </div>
    </div>

    <!-- File list -->
    <div class="card table-card">
      <h3 class="section-title">已上传文件</h3>
      <table class="table">
        <thead>
          <tr>
            <th>文件名</th>
            <th>类型</th>
            <th>块数</th>
            <th>上传时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="f in files" :key="f.id">
            <td class="font-mono text-sm">{{ f.filename }}</td>
            <td><span class="badge badge-accent">{{ f.file_type }}</span></td>
            <td>{{ f.chunk_count }}</td>
            <td class="text-sm text-secondary">{{ formatTime(f.created_at) }}</td>
            <td>
              <button class="btn btn-ghost btn-sm" @click="handleDelete(f.id)">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
                删除
              </button>
            </td>
          </tr>
          <tr v-if="files.length === 0">
            <td colspan="5" class="table-empty text-secondary">暂无上传文件</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { uploadFile, getUploadedFiles, deleteUploadedFile, type UploadedFile } from '@/api/upload'

const dragging = ref(false)
const files = ref<UploadedFile[]>([])

interface QueueItem {
  file: File
  status: 'pending' | 'uploading' | 'done' | 'error'
  result?: UploadedFile
  error?: string
}

const uploadQueue = ref<QueueItem[]>([])

onMounted(loadFiles)

async function loadFiles() {
  try {
    const { data } = await getUploadedFiles()
    files.value = data
  } catch (err) {
    console.error(err)
  }
}

async function uploadFiles(fileList: FileList) {
  const allowed = ['.py', '.js', '.java', '.md', '.txt', '.pdf']
  for (const file of Array.from(fileList)) {
    const ext = '.' + file.name.split('.').pop()?.toLowerCase()
    if (!allowed.includes(ext)) continue

    const item: QueueItem = { file, status: 'pending' }
    uploadQueue.value.push(item)
  }

  for (const item of uploadQueue.value) {
    if (item.status !== 'pending') continue
    item.status = 'uploading'
    try {
      const { data } = await uploadFile(item.file)
      item.status = 'done'
      item.result = data
    } catch (err: any) {
      item.status = 'error'
      item.error = err.response?.data?.detail || err.message
    }
  }
  await loadFiles()
}

function handleDrop(e: DragEvent) {
  dragging.value = false
  if (e.dataTransfer?.files) uploadFiles(e.dataTransfer.files)
}

function handleFileSelect(e: Event) {
  const input = e.target as HTMLInputElement
  if (input.files) uploadFiles(input.files)
  input.value = ''
}

async function handleDelete(fileId: number) {
  try {
    await deleteUploadedFile(fileId)
    await loadFiles()
  } catch (err) {
    console.error(err)
  }
}

function formatTime(ts: string) {
  return new Date(ts).toLocaleString('zh-CN')
}
</script>

<style scoped>
.page { padding: 24px; max-width: 960px; margin: 0 auto; }
.page-header { margin-bottom: 24px; }
.page-title { font-size: 1.4rem; font-weight: 700; letter-spacing: -0.02em; margin-bottom: 4px; }
.page-desc { margin: 0; }

.upload-zone {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px 20px;
  border: 2px dashed var(--border);
  border-radius: var(--radius-lg);
  cursor: pointer;
  transition: all 0.15s;
  margin-bottom: 20px;
}
.upload-zone:hover, .upload-zone--active {
  border-color: var(--primary);
  background: var(--primary-subtle);
}
.upload-icon { color: var(--text-muted); margin-bottom: 12px; }
.upload-zone:hover .upload-icon, .upload-zone--active .upload-icon { color: var(--primary-hover); }
.upload-text { font-size: 0.95rem; font-weight: 500; margin-bottom: 4px; }
.upload-hint { margin-bottom: 16px; }
.upload-btn { cursor: pointer; }

.upload-queue { display: flex; flex-direction: column; gap: 8px; margin-bottom: 24px; }
.queue-item { display: flex; align-items: center; justify-content: space-between; padding: 12px 16px; }
.queue-info { display: flex; flex-direction: column; gap: 2px; }
.queue-status { display: flex; align-items: center; gap: 8px; }

.spinner-sm {
  width: 16px; height: 16px;
  border: 2px solid var(--border);
  border-top-color: var(--primary);
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
.text-error { color: var(--error); }

.section-title { font-size: 0.95rem; font-weight: 600; margin-bottom: 12px; }
.table-card { padding: 20px; overflow-x: auto; }
.table { width: 100%; border-collapse: collapse; }
.table th {
  padding: 10px 12px;
  text-align: left;
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--text-muted);
  border-bottom: 1px solid var(--border);
}
.table td {
  padding: 10px 12px;
  font-size: 0.9rem;
  border-bottom: 1px solid var(--border);
}
.table tr:last-child td { border-bottom: none; }
.table tr:hover td { background: rgba(255,255,255,0.02); }
.table-empty { text-align: center; padding: 24px 12px !important; }
</style>
