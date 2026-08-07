# Types for RAG Smart Query Frontend

export interface User {
  id: string
  username: string
  email: string
  full_name: string | null
  role: string
  is_active: boolean
}

export interface KnowledgeBase {
  id: string
  name: string
  description: string | null
  status: 'draft' | 'indexing' | 'ready' | 'error'
  doc_count: number
  chunk_count: number
  embedding_model: string
}

export interface DataSource {
  id: string
  name: string
  db_type: string
  status: 'active' | 'inactive' | 'error'
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  type: 'text' | 'mixed'
  sources?: SourceRef[]
  sql?: string
  chartConfig?: ChartConfig
  resultData?: ResultData
}

export interface SourceRef {
  doc_title: string
  document_id: string
  score?: number
}

export interface ChartConfig {
  type: 'bar' | 'line' | 'pie' | 'bar_horizontal' | 'table' | 'number' | 'none'
  config: Record<string, any>
}

export interface ResultData {
  columns: string[]
  rows: any[][]
  row_count: number
  executed_sql?: string
  execution_time_ms?: number
}
