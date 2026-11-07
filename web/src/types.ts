export type MessageRole = 'user' | 'assistant' | 'system'

export interface ChatMessage {
  id: string
  role: MessageRole
  content: string
  streaming?: boolean
}

export interface InspectorEvent {
  id: string
  type: string
  timestamp?: string
  summary: string
  payload?: unknown
}