/** RAG Chat page — knowledge base Q&A interface */

import { useState, useEffect, useRef } from 'react'
import { Input, Button, Select, Empty, Spin, List, Tag, Space, Modal, Upload, message } from 'antd'
import { SendOutlined, PlusOutlined, FileTextOutlined, DeleteOutlined, UploadOutlined } from '@ant-design/icons'
import ChatMessage from '../../components/ChatMessage'
import { useChatStore } from '../../stores/useChatStore'
import { streamChat } from '../../api/client'
import client from '../../api/client'

const { TextArea } = Input

export default function RagChat() {
  const [input, setInput] = useState('')
  const [knowledgeBases, setKnowledgeBases] = useState<any[]>([])
  const [loadingKbs, setLoadingKbs] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const {
    messages,
    isStreaming,
    selectedKbId,
    addMessage,
    appendToLastAssistant,
    updateLastAssistantMetadata,
    clearMessages,
    setStreaming,
    setSelectedKb,
  } = useChatStore()

  useEffect(() => {
    loadKnowledgeBases()
  }, [])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  async function loadKnowledgeBases() {
    setLoadingKbs(true)
    try {
      const res = await client.get('/knowledge-bases')
      setKnowledgeBases(res.data)
      if (res.data.length > 0 && !selectedKbId) {
        setSelectedKb(res.data[0].id)
      }
    } catch {}
    setLoadingKbs(false)
  }

  async function handleSend() {
    if (!input.trim() || !selectedKbId || isStreaming) return

    const userMsg = input.trim()
    setInput('')

    addMessage({ id: Date.now().toString(), role: 'user', content: userMsg, type: 'text' })
    setStreaming(true)

    try {
      for await (const event of streamChat({
        engine: 'rag',
        message: userMsg,
        kb_id: selectedKbId,
      })) {
        switch (event.type) {
          case 'retrieval_result':
            updateLastAssistantMetadata({ sources: event.data.sources })
            break
          case 'message_delta':
            appendToLastAssistant(event.data.content)
            break
          case 'message_done':
            updateLastAssistantMetadata({
              sources: event.data.metadata?.sources,
              tokensUsed: event.data.usage?.total_tokens,
            })
            break
        }
      }
    } catch (err: any) {
      appendToLastAssistant(`❌ 错误: ${err.message || '请求失败'}`)
    }

    setStreaming(false)
  }

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* Toolbar */}
      <div style={{
        display: 'flex',
        gap: 12,
        alignItems: 'center',
        padding: '12px 16px',
        background: '#fff',
        borderRadius: 8,
        boxShadow: '0 1px 3px rgba(0,0,0,0.08)',
        marginBottom: 12,
      }}>
        <Space>
          <FileTextOutlined style={{ fontSize: 18 }} />
          <span style={{ fontWeight: 600 }}>选择知识库:</span>
        </Space>
        <Select
          value={selectedKbId}
          onChange={setSelectedKb}
          style={{ width: 260 }}
          placeholder="请选择知识库"
          loading={loadingKbs}
          options={knowledgeBases.map((kb) => ({
            label: `${kb.name} (${kb.doc_count}文档)`,
            value: kb.id,
          }))}
        />

        <Button icon={<PlusOutlined />} onClick={() => window.location.href = '/knowledge'}>
          新建知识库
        </Button>

        <Button
          danger
          icon={<DeleteOutlined />}
          onClick={() => {
            if (confirm('确定清空当前对话？')) clearMessages()
          }}
        >
          清空对话
        </Button>
      </div>

      {/* Messages */}
      <div
        style={{
          flex: 1,
          overflowY: 'auto',
          padding: '0 8px',
          minHeight: 300,
        }}
      >
        {messages.length === 0 ? (
          <Empty
            description="开始提问吧！选择一个知识库后输入您的问题。"
            style={{ marginTop: 120 }}
          >
            <Button type="primary" onClick={() => document.getElementById('rag-input')?.focus()}>
              开始对话
            </Button>
          </Empty>
        ) : (
          messages.map((msg) => (
            <ChatMessage
              key={msg.id}
              role={msg.role}
              content={msg.content}
              sources={msg.sources}
              isStreaming={isStreaming && msg.role === 'assistant'}
            />
          ))
        )}
        {isStreaming && (
          <div style={{ padding: '8px 48px' }}>
            <Spin size="small" /> <span style={{ color: '#999', marginLeft: 8 }}>正在思考...</span>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div
        style={{
          display: 'flex',
          gap: 8,
          padding: '12px 0 0',
          borderTop: '1px solid #f0f0f0',
          paddingTop: 12,
        }}
      >
        <TextArea
          id="rag-input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onPressEnter={(e) => {
            if (!e.shiftKey) {
              e.preventDefault()
              handleSend()
            }
          }}
          placeholder="输入您的问题（Shift+Enter换行）..."
          autoSize={{ minRows: 1, maxRows: 4 }}
          disabled={!selectedKbId || isStreaming}
        />
        <Button
          type="primary"
          icon={<SendOutlined />}
          onClick={handleSend}
          disabled={!input.trim() || !selectedKbId || isStreaming}
          style={{ alignSelf: 'flex-end' }}
        >
          发送
        </Button>
      </div>
    </div>
  )
}
