import { create } from 'zustand'
import type { ChatMessage, InspectorEvent } from '../types'

interface ChatState {
  messages: ChatMessage[]
  inspector: InspectorEvent[]
  status: string
  sidebarOpen: boolean
  inspectorOpen: boolean
  addMessage: (m: ChatMessage) => void
  appendToken: (id: string, token: string) => void
  finalizeMessage: (id: string) => void
  addInspectorEvent: (e: InspectorEvent) => void
  setStatus: (s: string) => void
  reset: () => void
  toggleSidebar: () => void
  toggleInspector: () => void
}

export const useChatStore = create<ChatState>((set) => ({
  messages: [],
  inspector: [],
  status: 'idle',
  sidebarOpen: true,
  inspectorOpen: true,
  addMessage: (m) => set((s) => ({ messages: [...s.messages, m] })),
  appendToken: (id, token) =>
    set((s) => ({
      messages: s.messages.map((m) => (m.id === id ? { ...m, content: m.content + token } : m)),
    })),
  finalizeMessage: (id) =>
    set((s) => ({
      messages: s.messages.map((m) => (m.id === id ? { ...m, streaming: false } : m)),
    })),
  addInspectorEvent: (e) =>
    set((s) => ({ inspector: [...s.inspector.slice(-299), e] })),
  setStatus: (status) => set({ status }),
  reset: () => set({ messages: [], inspector: [], status: 'idle' }),
  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
  toggleInspector: () => set((s) => ({ inspectorOpen: !s.inspectorOpen })),
}))