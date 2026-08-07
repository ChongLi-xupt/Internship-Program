/**
 * Smart Query Page — SQLBot-style NL2SQL interface
 *
 * Layout (matching SQLBot reference):
 * ┌─────────────────────────────────────────────┐
 * │ [Data Source Selector] [Clear]              │
 * ├─────────────────────────────────────────────┤
 * │ [Input: 自然语言问题...]          [发送 ▶]   │
 * ├──────────────────┬──────────────────────────┤
 * │ Message History   │ Active Response Panel    │
 * │                    │                         │
 * │  User: 各区域销..  │ 📊 Analysis Text        │
 * │                    │                         │
 * │  Assistant:        │ ┌─ SQL Panel ─┐       │
 * │  [Analysis text]   │ │ SELECT ...   │       │
 * │                    │ └──────────────┘       │
 * │                    │                         │
 * │                    │ ┌─ Data Table ─┐       │
 * │                    │ │ Region | $   │       │
 * │                    │ │ 东部   |123K│       │
 * │                    │ └──────────────┘       │
 * │                    │                         │
 * │                    │ ┌─ Chart ──────┐       │
 * │                    │ │ ████ bar     │       │
 * │                    │ └──────────────┘       │
 * └────────────────────┴─────────────────────────┘
 */

import { useState, useEffect, useRef } from 'react'
import {
  Input,
  Button,
  Select,
  Empty,
  Spin,
  Space,
  Tag,
  Collapse,
  Card,
  Tooltip,
} from 'antd'
import {
  SendOutlined,
  PlusOutlined,
  DatabaseOutlined,
  DeleteOutlined,
  CodeOutlined,
  TableOutlined,
  BarChartOutlined,
  LoadingOutlined,
} from '@ant-design/icons'
import ChatMessage from '../../components/ChatMessage'
import ChartPanel from '../../components/ChartPanel'
import { useChatStore } from '../../stores/useChatStore'
import { streamChat } from '../../api/client'
import client from '../../api/client'

const { TextArea } = Input

export default function SmartQuery() {
  const [input, setInput] = useState('')
  const [datasources, setDatasources] = useState<any[]>([])
  const [loadingDs, setLoadingDs] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // Current response being assembled from SSE events
  const [currentSql, setCurrentSql] = useState<string>('')
  const [currentResultData, setCurrentResultData] = useState<any>(null)
  const [currentChartConfig, setCurrentChartConfig] = useState<any>(null)
  const [currentIntent, setCurrentIntent] = useState<any>(null)
  const [statusText, setStatusText] = useState('')

  const {
    messages,
    isStreaming,
    selectedDsId,
    addMessage,
    appendToLastAssistant,
    updateLastAssistantMetadata,
    clearMessages,
    setStreaming,
    setSelectedDs,
  } = useChatStore()

  useEffect(() => {
    loadDatasources()
  }, [])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  async function loadDatasources() {
    setLoadingDs(true)
    try {
      const res = await client.get('/datasources')
      setDatasources(res.data)
      if (res.data.length > 0 && !selectedDsId) {
        setSelectedDs(res.data[0].id)
      }
    } catch {}
    setLoadingDs(false)
  }

  function resetCurrentResponse() {
    setCurrentSql('')
    setCurrentResultData(null)
    setCurrentChartConfig(null)
    setCurrentIntent(null)
    setStatusText('')
  }

  async function handleSend() {
    if (!input.trim() || !selectedDsId || isStreaming) return

    const userMsg = input.trim()
    setInput('')
    resetCurrentResponse()

    addMessage({ id: Date.now().toString(), role: 'user', content: userMsg, type: 'text' })
    setStreaming(true)

    try {
      for await (const event of streamChat({
        engine: 'query',
        message: userMsg,
        datasource_id: selectedDsId,
      })) {
        switch (event.type) {
          case 'thinking':
            setStatusText(event.data.content || '')
            break

          case 'query_intent':
            if (event.data.intent?.metrics) {
              setCurrentIntent(event.data.intent)
              setStatusText('已识别查询意图，正在生成 SQL...')
            }
            break

          case 'sql_generated':
            setCurrentSql(event.data.sql)
            setStatusText('SQL 已生成，正在执行...')
            break

          case 'sql_executing':
            setStatusText('正在执行查询...')
            break

          case 'result_data':
            setCurrentResultData(event.data)
            setStatusText('查询完成，正在分析结果...')
            break

          case 'chart_recommendation':
            setCurrentChartConfig(event.data)
            break

          case 'message_delta':
            appendToLastAssistant(event.data.content)
            break

          case 'message_done':
            if (event.data.metadata?.error) {
              appendToLastAssistant(`\n\n⚠️ ${event.data.metadata.error}`)
            }
            updateLastAssistantMetadata({
              sql: currentSql,
              chartConfig: currentChartConfig,
              resultData: currentResultData,
              tokensUsed: event.data.usage?.total_tokens,
            })
            setStatusText('')
            break
        }
      }
    } catch (err: any) {
      appendToLastAssistant(`❌ 错误: ${err.message || '请求失败'}`)
      setStatusText('')
    }

    setStreaming(false)
  }

  /** Quick query suggestions based on semantic layer */
  const quickQueries = [
    '各区域销售额排名',
    '近30天订单趋势',
    '产品类别销售占比',
    'Top10 客户消费排行',
    '本月 vs 上月对比',
  ]

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
        flexWrap: 'wrap',
      }}>
        <Space>
          <DatabaseOutlined style={{ fontSize: 18 }} />
          <span style={{ fontWeight: 600 }}>数据源:</span>
        </Space>

        <Select
          value={selectedDsId}
          onChange={setSelectedDs}
          style={{ width: 240 }}
          placeholder="选择数据源"
          loading={loadingDs}
          options={datasources.map((ds) => ({
            label: `${ds.name} (${ds.db_type})`,
            value: ds.id,
          }))}
        />

        <Button icon={<PlusOutlined />} onClick={() => window.location.href = '/data/datasources'}>
          新建数据源
        </Button>

        <Button danger icon={<DeleteOutlined />} onClick={() => { if (confirm('清空对话？')) clearMessages(); resetCurrentResponse() }}>
          清空
        </Button>

        {isStreaming && (
          <Tag color="processing" icon={<LoadingOutlined spin />}>
            {statusText || '处理中...'}
          </Tag>
        )}
      </div>

      {/* Main area */}
      <div style={{ flex: 1, display: 'flex', gap: 12, minHeight: 400 }}>
        {/* Left: Conversation history - 缩小宽度 */}
        <div
          style={{
            width: 240,
            minWidth: 200,
            display: 'flex',
            flexDirection: 'column',
            borderRight: '1px solid #f0f0f0',
            paddingRight: 8,
          }}
        >
          {messages.length === 0 ? (
            <Empty description="输入问题开始查询" image={Empty.PRESENTED_IMAGE_SIMPLE} style={{ marginTop: 60 }}>
              <div style={{ marginTop: 8 }}>
                <p style={{ color: '#666', fontSize: 12, marginBottom: 6 }}>💡 快速查询:</p>
                <Space size={[4, 4]} wrap direction="vertical" style={{ width: '100%' }}>
                  {quickQueries.slice(0, 3).map((q) => (
                    <Tag
                      key={q}
                      style={{ cursor: 'pointer', padding: '2px 6px', fontSize: 11 }}
                      onClick={() => { setInput(q); }}
                      color="blue"
                    >
                      {q}
                    </Tag>
                  ))}
                </Space>
              </div>
            </Empty>
          ) : (
            <div style={{ overflowY: 'auto', flex: 1 }}>
              {messages.map((msg) => (
                <ChatMessage
                  key={msg.id}
                  role={msg.role}
                  content={msg.content}
                  sql={msg.sql}
                  resultData={msg.resultData}
                  chartConfig={msg.chartConfig}
                  sources={msg.sources}
                  isStreaming={false}
                />
              ))}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Right: Current response panel - 扩大区域，始终显示 */}
        <div
          style={{
            flex: 1,
            overflowY: 'auto',
            background: '#fafafa',
            borderRadius: 8,
            padding: 12,
            display: 'flex',
            flexDirection: 'column',
            gap: 10,
          }}
        >
          {/* 默认提示 */}
          {!currentSql && !currentResultData && !isStreaming && messages.length === 0 && (
            <Empty
              description="请输入自然语言问题开始查询"
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              style={{ marginTop: 100 }}
            >
              <p style={{ color: '#888', fontSize: 13, marginTop: 8 }}>
                支持自然语言转SQL、自动执行查询、智能生成图表
              </p>
            </Empty>
          )}

          {/* Intent badge */}
          {currentIntent && (
            <Tooltip title={JSON.stringify(currentIntent, null, 2)}>
              <Tag color="purple" style={{ fontSize: 13, padding: '4px 12px' }}>
                🔍 意图: {currentIntent.type || '聚合查询'}
                {currentIntent.metrics?.length > 0 &&
                  ` → ${currentIntent.metrics.map((m: any) => m.name).join(', ')}`}
              </Tag>
            </Tooltip>
          )}

          {/* SQL Panel */}
          {currentSql && (
            <Card
              size="small"
              title={
                <Space>
                  <CodeOutlined />
                  <span>生成的 SQL</span>
                </Space>
              }
              style={{ borderRadius: 6 }}
            >
              <pre
                style={{
                  background: '#1e1e1e',
                  color: '#d4d4d4',
                  padding: 12,
                  borderRadius: 4,
                  fontSize: 12.5,
                  overflowX: 'auto',
                  margin: 0,
                  lineHeight: 1.5,
                }}
              >
                <code>{currentSql}</code>
              </pre>
            </Card>
          )}

          {/* Data Table */}
          {currentResultData?.rows?.length > 0 && (
            <Card
              size="small"
              title={
                <Space>
                  <TableOutlined />
                  <span>查询结果 ({currentResultData.row_count} 条)</span>
                  {currentResultData.execution_time_ms != null && (
                    <Tag color="default">{currentResultData.execution_time_ms.toFixed(0)}ms</Tag>
                  )}
                </Space>
              }
              style={{ borderRadius: 6 }}
            >
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                <thead>
                  <tr>
                    {currentResultData.columns.map((col: string) => (
                      <th
                        key={col}
                        style={{
                          background: '#f5f5f5',
                          padding: '7px 10px',
                          borderBottom: '2px solid #e8e8e8',
                          textAlign: 'left',
                          fontWeight: 600,
                          position: 'sticky',
                          top: 0,
                        }}
                      >
                        {col}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {currentResultData.rows.slice(0, 50).map((row: any[], i: number) => (
                    <tr key={i}>
                      {row.map((cell: any, j: number) => (
                        <td
                          key={j}
                          style={{
                            padding: '5px 10px',
                            borderBottom: '1px solid #f5f5f5',
                            whiteSpace: j === 0 ? 'nowrap' : 'normal',
                          }}
                        >
                          {cell != null ? String(cell) : <span style={{ color: '#bbb' }}>NULL</span>}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
              {currentResultData.rows.length > 50 && (
                <div style={{ textAlign: 'center', color: '#999', marginTop: 8, fontSize: 12 }}>
                  显示前 50 / 共 {currentResultData.rows.length} 条
                </div>
              )}
            </Card>
          )}

          {/* Chart */}
          {currentChartConfig && currentResultData && (
            <ChartPanel
              type={currentChartConfig.type}
              config={currentChartConfig.config || {}}
              data={currentResultData}
            />
          )}

          {/* Streaming status */}
          {isStreaming && !currentResultData && (
            <div style={{ textAlign: 'center', padding: 20 }}>
              <Spin indicator={<LoadingOutlined style={{ fontSize: 24 }} spin />} />
              <p style={{ color: '#666', marginTop: 8 }}>{statusText || '正在处理...'}</p>
            </div>
          )}
        </div>
      </div>

      {/* Input bar */}
      <div style={{ display: 'flex', gap: 8, paddingTop: 12, borderTop: '1px solid #f0f0f0' }}>
        <TextArea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onPressEnter={(e) => {
            if (!e.shiftKey) { e.preventDefault(); handleSend() }
          }}
          placeholder="🔍 用自然语言描述您的查询需求，例如：'各区域上月销售额对比'"
          autoSize={{ minRows: 1, maxRows: 3 }}
          disabled={!selectedDsId || isStreaming}
        />
        <Button
          type="primary"
          icon={<SendOutlined />}
          onClick={handleSend}
          disabled={!input.trim() || !selectedDsId || isStreaming}
          style={{ alignSelf: 'flex-end', height: 38 }}
        >
          查询
        </Button>
      </div>
    </div>
  )
}
