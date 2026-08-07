/** Chat store — manages active conversation state */

import { create } from 'zustand'

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  type: 'text' | 'mixed'
  metadata?: any
  sources?: any[]
  sql?: string
  chartConfig?: any
  resultData?: any
}

interface ChatState {
  messages: Message[]
  isStreaming: boolean
  currentEngine: 'rag' | 'query'
  selectedKbId: string | null
  selectedDsId: string | null
  conversationId: string | null

  addMessage: (msg: Message) => void
  appendToLastAssistant: (text: string) => void
  updateLastAssistantMetadata: (meta: any) => void
  clearMessages: () => void
  setStreaming: (v: boolean) => void
  setEngine: (e: 'rag' | 'query') => void
  setSelectedKb: (id: string | null) => void
  setSelectedDs: (id: string | null) => void
}

export const useChatStore = create<ChatState>((set) => ({
  messages: [],
  isStreaming: false,
  currentEngine: 'rag',
  selectedKbId: null,
  selectedDsId: null,
  conversationId: null,

  addMessage: (msg) =>
    set((s) => ({ messages: [...s.messages, msg] })),

  appendToLastAssistant: (text) =>
    set((s) => {
      const msgs = [...s.messages]
      const last = msgs[msgs.length - 1]
      if (last?.role === 'assistant') {
        msgs[msgs.length - 1] = { ...last, content: last.content + text }
      } else {
        msgs.push({ id: Date.now().toString(), role: 'assistant', content: text, type: 'text' })
      }
      return { messages: msgs }
    }),

  updateLastAssistantMetadata: (meta) =>
    set((s) => {
      const msgs = [...s.messages]
      const last = msgs[msgs.length - 1]
      if (last?.role === 'assistant') {
        msgs[msgs.length - 1] = { ...last, ...meta }
      }
      return { messages: msgs }
    }),

  clearMessages: () =>
    set({ messages: [], conversationId: null }),
  setStreaming: (v) => set({ isStreaming: v }),
  setEngine: (e) => set({ currentEngine: e }),
  setSelectedKb: (id) => set({ selectedKbId: id }),
  setSelectedDs: (id) => set({ selectedDsId: id }),
}))
