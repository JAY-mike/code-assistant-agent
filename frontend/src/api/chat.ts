import api from './client'

export interface MessageItem {
  id: number
  session_id: string
  role: 'user' | 'assistant'
  content: string
  tool_calls?: any
  created_at: string
}

export interface SessionItem {
  session_id: string
  title?: string
  created_at: string
  updated_at: string
  message_count?: number
}

/** 发送消息（同步，等待完整回复） */
export function sendMessage(sessionId: string, content: string) {
  return api.post<MessageItem>('/chat/message', { session_id: sessionId, content })
}

/** 发送消息，SSE 流式响应（fetch 原生） */
export function sendMessageStream(
  sessionId: string,
  content: string,
  onChunk: (text: string) => void,
  onDone: () => void,
  onError: (err: any) => void,
): AbortController {
  const controller = new AbortController()
  const token = localStorage.getItem('access_token')

  fetch(`/api/chat/stream?session_id=${sessionId}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ session_id: sessionId, content }),
    signal: controller.signal,
  })
    .then(async (res) => {
      if (!res.ok || !res.body) throw new Error('Stream unavailable')
      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const payload = line.slice(6)
            if (payload === '[DONE]') {
              onDone()
              return
            }
            try {
              const parsed = JSON.parse(payload)
              if (parsed.type === 'token') onChunk(parsed.content)
              if (parsed.type === 'thinking') onChunk(parsed.content)
              if (parsed.type === 'tool_call') onChunk(`\n\`\`\`[工具调用] ${parsed.tool}\`\`\`\n${parsed.input || ''}`)
              if (parsed.type === 'tool_result') onChunk(`\n\`\`\`[工具结果] ${parsed.tool}\`\`\`\n${parsed.result || ''}`)
            } catch {
              onChunk(payload)
            }
          }
        }
      }
      onDone()
    })
    .catch((err) => {
      if (err.name !== 'AbortError') onError(err)
    })

  return controller
}

/** 获取历史会话列表 */
export function getSessions(page = 1, pageSize = 20) {
  return api.get<{ sessions: SessionItem[]; total: number }>('/chat/sessions', {
    params: { page, page_size: pageSize },
  })
}

/** 获取会话消息 */
export function getMessages(sessionId: string) {
  return api.get<MessageItem[]>(`/chat/sessions/${sessionId}/messages`)
}

/** 删除会话 */
export function deleteSession(sessionId: string) {
  return api.delete(`/chat/sessions/${sessionId}`)
}
