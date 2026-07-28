import api from './client'

export interface FeedbackReq {
  message_id: number
  session_id: string
  rating: 1 | -1
  comment?: string
}

export function submitFeedback(data: FeedbackReq) {
  return api.post('/feedback', data)
}
