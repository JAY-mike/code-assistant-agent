<template>
  <div
    class="message"
    :class="[`message--${role}`, { 'message--streaming': streaming }]"
  >
    <div class="message-avatar">{{ role === 'assistant' ? 'A' : 'U' }}</div>
    <div class="message-body">
      <div class="message-role">{{ role === 'assistant' ? 'Agent' : '你' }}</div>
      <div class="message-content" v-if="role === 'assistant' && !streaming">
        <MarkdownRenderer :content="content" />
      </div>
      <div class="message-content" v-else-if="role === 'assistant' && streaming">
        <MarkdownRenderer :content="content" />
        <span class="cursor">▊</span>
      </div>
      <div class="message-content" v-else>
        <div class="message-plain">{{ content }}</div>
      </div>
      <div class="message-meta" v-if="createdAt && !streaming">
        <span class="text-xs text-muted">{{ formatTime(createdAt) }}</span>
        <slot name="actions" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import MarkdownRenderer from './MarkdownRenderer.vue'

const props = defineProps<{
  role: 'user' | 'assistant'
  content: string
  createdAt?: string
  streaming?: boolean
}>()

function formatTime(ts: string) {
  const d = new Date(ts)
  return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}
</script>

<style scoped>
.message {
  display: flex;
  gap: 12px;
  padding: 16px 20px;
  transition: background 0.15s;
}
.message:hover { background: rgba(255,255,255,0.02); }
.message--assistant { background: rgba(255,255,255,0.03); }

.message-avatar {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.8rem;
  font-weight: 700;
  flex-shrink: 0;
  margin-top: 2px;
}
.message--user .message-avatar { background: var(--primary); color: #fff; }
.message--assistant .message-avatar { background: var(--accent-subtle); color: var(--accent); }

.message-body { flex: 1; min-width: 0; }
.message-role { font-size: 0.85rem; font-weight: 600; margin-bottom: 4px; color: var(--text-primary); }
.message-content { font-size: 0.92rem; line-height: 1.65; }
.message-plain { white-space: pre-wrap; }
.message-meta { display: flex; align-items: center; gap: 8px; margin-top: 8px; }

.cursor {
  display: inline-block;
  color: var(--primary-hover);
  animation: blink 0.8s step-end infinite;
  margin-left: 2px;
}
@keyframes blink {
  50% { opacity: 0; }
}
</style>
