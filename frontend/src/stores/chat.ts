import { defineStore } from 'pinia'
import { ref } from 'vue'
import { sendMessageStream, getSessions, getMessages, deleteSession, type SessionItem, type MessageItem } from '@/api/chat'

export const useChatStore = defineStore('chat', () => {
  const sessions = ref<SessionItem[]>([])
  const currentSessionId = ref<string>('')
  const messages = ref<MessageItem[]>([])
  const isStreaming = ref(false)
  const abortController = ref<AbortController | null>(null)

  const streamingContent = ref('')

  async function loadSessions() {
    const { data } = await getSessions()
    sessions.value = data.sessions
  }

  async function loadMessages(sessionId: string) {
    currentSessionId.value = sessionId
    const { data } = await getMessages(sessionId)
    messages.value = data
  }

  async function createSession(): Promise<string> {
    const id = `session_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
    currentSessionId.value = id
    messages.value = []
    await loadSessions()
    return id
  }

  async function sendMessage(content: string) {
    if (!currentSessionId.value) {
      await createSession()
    }
    messages.value.push({
      id: -Date.now(),
      session_id: currentSessionId.value,
      role: 'user',
      content,
      created_at: new Date().toISOString(),
    })

    isStreaming.value = true
    streamingContent.value = ''

    abortController.value = sendMessageStream(
      currentSessionId.value,
      content,
      (chunk) => {
        streamingContent.value += chunk
      },
      () => {
        const finalContent = streamingContent.value
        messages.value.push({
          id: Date.now(),
          session_id: currentSessionId.value,
          role: 'assistant',
          content: finalContent,
          created_at: new Date().toISOString(),
        })
        streamingContent.value = ''
        isStreaming.value = false
        abortController.value = null
        loadSessions()
      },
      (err) => {
        console.error('Stream error:', err)
        isStreaming.value = false
        abortController.value = null
      },
    )
  }

  function stopStreaming() {
    abortController.value?.abort()
    isStreaming.value = false
    abortController.value = null
    if (streamingContent.value) {
      messages.value.push({
        id: Date.now(),
        session_id: currentSessionId.value,
        role: 'assistant',
        content: streamingContent.value,
        created_at: new Date().toISOString(),
      })
      streamingContent.value = ''
    }
  }

  async function removeSession(sessionId: string) {
    await deleteSession(sessionId)
    sessions.value = sessions.value.filter((s) => s.session_id !== sessionId)
    if (currentSessionId.value === sessionId) {
      currentSessionId.value = ''
      messages.value = []
    }
  }

  return {
    sessions, currentSessionId, messages, isStreaming, streamingContent,
    loadSessions, loadMessages, createSession, sendMessage, stopStreaming, removeSession,
  }
})
