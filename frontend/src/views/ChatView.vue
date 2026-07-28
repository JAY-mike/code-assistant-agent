<template>
  <div class="chat-layout">
    <!-- Session sidebar -->
    <aside class="sessions-panel">
      <div class="sessions-header">
        <h3 class="sessions-title">历史会话</h3>
        <button class="btn btn-primary btn-sm" @click="handleNewChat">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
          新对话
        </button>
      </div>

      <div class="sessions-list">
        <div
          v-for="s in chat.sessions"
          :key="s.session_id"
          class="session-item"
          :class="{ 'session-item--active': s.session_id === chat.currentSessionId }"
          @click="handleSelectSession(s.session_id)"
        >
          <div class="session-icon">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
          </div>
          <div class="session-info">
            <div class="session-preview truncate">{{ s.title || '新对话' }}</div>
            <div class="session-time text-xs text-muted">{{ formatTime(s.updated_at) }}</div>
          </div>
          <button class="btn btn-ghost btn-icon session-del" @click.stop="handleDelete(s.session_id)" title="删除">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
          </button>
        </div>
        <div v-if="chat.sessions.length === 0" class="sessions-empty text-secondary text-sm">
          暂无历史会话
        </div>
      </div>
    </aside>

    <!-- Chat area -->
    <div class="chat-main">
      <!-- Messages -->
      <div class="messages-area" ref="messagesRef">
        <div v-if="chat.messages.length === 0 && !chat.isStreaming" class="welcome">
          <div class="welcome-icon">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="16 3 21 3 21 8" />
              <line x1="4" y1="20" x2="21" y2="3" />
              <polyline points="21 16 21 21 16 21" />
              <line x1="15" y1="15" x2="21" y2="21" />
              <line x1="4" y1="4" x2="9" y2="9" />
            </svg>
          </div>
          <h2 class="welcome-title">Code Assistant Agent</h2>
          <p class="welcome-desc">基于 RAG 的代码智能分析助手。上传代码库、检索代码片段、回答问题、Agent 自动分析。</p>
          <div class="welcome-hints">
            <div class="hint-card" @click="handleQuickAsk('这段代码的主要功能是什么？')">
              <span class="hint-icon">🔍</span>
              <span>分析代码功能</span>
            </div>
            <div class="hint-card" @click="handleQuickAsk('解释这个项目中的核心类设计')">
              <span class="hint-icon">📐</span>
              <span>解释类设计</span>
            </div>
            <div class="hint-card" @click="handleQuickAsk('这个代码有什么可以优化的地方？')">
              <span class="hint-icon">⚡</span>
              <span>代码优化建议</span>
            </div>
          </div>
        </div>

        <template v-for="msg in chat.messages" :key="msg.id">
          <MessageBubble
            :role="msg.role"
            :content="msg.content"
            :created-at="msg.created_at"
          />
        </template>

        <!-- Streaming message -->
        <MessageBubble
          v-if="chat.isStreaming"
          role="assistant"
          :content="chat.streamingContent"
          :streaming="true"
        />
      </div>

      <!-- Input area -->
      <div class="input-area">
        <div class="input-row">
          <textarea
            v-model="inputText"
            class="input chat-input"
            placeholder="输入你的问题，如：解释 TinyDB 的 document 类..."
            rows="1"
            @keydown.enter.exact.prevent="handleSend"
            @input="autoResize"
          ></textarea>
          <div class="input-actions">
            <button
              v-if="!chat.isStreaming"
              class="btn btn-primary btn-send"
              :disabled="!inputText.trim()"
              @click="handleSend"
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
            </button>
            <button v-else class="btn btn-ghost btn-send" @click="chat.stopStreaming()">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="6" width="12" height="12" rx="2"/></svg>
            </button>
          </div>
        </div>
        <p class="input-hint text-xs text-muted">Agent 会基于 RAG 检索结果分析代码并回答问题</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useChatStore } from '@/stores/chat'
import MessageBubble from '@/components/MessageBubble.vue'

const chat = useChatStore()
const route = useRoute()
const router = useRouter()

const inputText = ref('')
const messagesRef = ref<HTMLElement | null>(null)

onMounted(() => {
  chat.loadSessions()
  if (route.params.sessionId) {
    chat.loadMessages(route.params.sessionId as string)
  }
})

watch(() => chat.messages.length, () => scrollToBottom())
watch(() => chat.streamingContent, () => scrollToBottom())

function scrollToBottom() {
  nextTick(() => {
    if (messagesRef.value) {
      messagesRef.value.scrollTop = messagesRef.value.scrollHeight
    }
  })
}

async function handleSend() {
  const text = inputText.value.trim()
  if (!text || chat.isStreaming) return
  inputText.value = ''
  await chat.sendMessage(text)
}

function handleQuickAsk(text: string) {
  inputText.value = text
  handleSend()
}

async function handleNewChat() {
  const id = await chat.createSession()
  router.push(`/chat/${id}`)
}

async function handleSelectSession(sessionId: string) {
  router.push(`/chat/${sessionId}`)
  await chat.loadMessages(sessionId)
}

async function handleDelete(sessionId: string) {
  await chat.removeSession(sessionId)
  if (chat.sessions.length > 0) {
    router.push(`/chat/${chat.sessions[0].session_id}`)
  } else {
    router.push('/chat')
  }
}

function autoResize(e: Event) {
  const el = e.target as HTMLTextAreaElement
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 200) + 'px'
}

function formatTime(ts: string) {
  const d = new Date(ts)
  const now = new Date()
  const diff = now.getTime() - d.getTime()
  if (diff < 86400000) return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  return d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
}
</script>

<style scoped>
.chat-layout {
  display: flex;
  height: 100%;
}

/* ===== Sessions Panel ===== */
.sessions-panel {
  width: 240px;
  min-width: 240px;
  background: var(--bg-surface);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.sessions-header {
  padding: 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  border-bottom: 1px solid var(--border);
}
.sessions-title { font-size: 0.8rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; color: var(--text-muted); }
.sessions-list { flex: 1; overflow-y: auto; padding: 8px; }
.session-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: background 0.1s;
  margin-bottom: 2px;
}
.session-item:hover { background: var(--bg-hover); }
.session-item--active { background: var(--primary-subtle); }
.session-item--active .session-preview { color: var(--primary-hover); }

.session-icon {
  color: var(--text-muted);
  flex-shrink: 0;
}
.session-info { flex: 1; min-width: 0; }
.session-preview { font-size: 0.85rem; font-weight: 500; }
.session-time { margin-top: 2px; }
.session-del { opacity: 0; transition: opacity 0.1s; }
.session-item:hover .session-del { opacity: 1; }
.sessions-empty { padding: 24px 16px; text-align: center; }

/* ===== Chat Main ===== */
.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.messages-area {
  flex: 1;
  overflow-y: auto;
  padding: 16px 0;
}

/* Welcome */
.welcome {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 32px;
  text-align: center;
}
.welcome-icon {
  width: 72px;
  height: 72px;
  border-radius: 18px;
  background: var(--primary-subtle);
  color: var(--primary-hover);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 20px;
}
.welcome-title { font-size: 1.5rem; font-weight: 700; margin-bottom: 8px; letter-spacing: -0.02em; }
.welcome-desc { font-size: 0.9rem; color: var(--text-secondary); max-width: 480px; margin-bottom: 32px; line-height: 1.6; }

.welcome-hints {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  justify-content: center;
}
.hint-card {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all 0.15s;
  font-size: 0.85rem;
  color: var(--text-secondary);
}
.hint-card:hover {
  border-color: var(--primary);
  color: var(--text-primary);
  background: var(--primary-subtle);
}
.hint-icon { font-size: 1rem; }

/* Input */
.input-area {
  padding: 12px 20px 16px;
  border-top: 1px solid var(--border);
  background: var(--bg-primary);
}
.input-row {
  display: flex;
  gap: 8px;
  align-items: flex-end;
}
.chat-input {
  flex: 1;
  resize: none;
  min-height: 44px;
  max-height: 200px;
  padding: 12px 16px;
  border-radius: var(--radius-md);
}
.input-actions { flex-shrink: 0; padding-bottom: 2px; }
.btn-send {
  width: 44px;
  height: 44px;
  padding: 0;
  border-radius: var(--radius-md);
}
.input-hint { text-align: right; margin-top: 6px; padding-right: 4px; }
</style>
