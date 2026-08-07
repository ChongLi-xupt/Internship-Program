/** Chat message bubble component */

import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Card, Tag, Collapse } from 'antd'
import { UserOutlined, RobotOutlined } from '@ant-design/icons'

interface Props {
  role: 'user' | 'assistant'
  content: string
  sources?: Array<{ doc_title: string; document_id: string; score?: number }>
  sql?: string
  chartConfig?: any
  resultData?: { columns: string[]; rows: any[][] }
  isStreaming?: boolean
}

export default function ChatMessage({ role, content, sources, sql, chartConfig, resultData, isStreaming }: Props) {
  const isUser = role === 'user'

  return (
    <div style={{ display: 'flex', gap: 12, marginBottom: 16, flexDirection: isUser ? 'row-reverse' : 'row' }}>
      <Avatar
        style={{ backgroundColor: isUser ? '#87d068' : '#1677ff', flexShrink: 0 }}
        icon={isUser ? <UserOutlined /> : <RobotOutlined />}
      />

      <div style={{ maxWidth: '75%' }}>
        <Card
          size="small"
          style={{
            backgroundColor: isUser ? '#e6f4ff' : '#fff',
            borderRadius: 8,
            boxShadow: '0 1px 3px rgba(0,0,0,0.08)',
          }}
          bodyStyle={{ padding: '12px 16px' }}
        >
          {/* Text content */}
          <div className="markdown-body" style={{ lineHeight: 1.7 }}>
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {content || (isStreaming ? '正在思考...' : '')}
            </ReactMarkdown>
          </div>

          {/* SQL panel */}
          {sql && (
            <pre
              style={{
                marginTop: 12,
                background: '#1e1e1e',
                color: '#d4d4d4',
                padding: 10,
                borderRadius: 6,
                fontSize: 12,
                overflowX: 'auto',
              }}
            >
              <code>{sql}</code>
            </pre>
          )}

          {/* Data table */}
          {resultData?.rows?.length > 0 && (
            <div style={{ marginTop: 12 }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                <thead>
                  <tr>
                    {resultData.columns.map((col) => (
                      <th
                        key={col}
                        style={{
                          background: '#fafafa',
                          padding: '6px 10px',
                          borderBottom: '2px solid #eee',
                          textAlign: 'left',
                        }}
                      >
                        {col}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {resultData.rows.slice(0, 50).map((row, i) => (
                    <tr key={i}>
                      {row.map((cell: any, j: number) => (
                        <td key={j} style={{ padding: '5px 10px', borderBottom: '1px solid #f5f5f5' }}>
                          {String(cell ?? '')}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
              {resultData.rows.length > 50 && (
                <div style={{ textAlign: 'center', color: '#999', marginTop: 4, fontSize: 12 }}>
                  仅显示前 50 条，共 {resultData.rows.length} 条
                </div>
              )}
            </div>
          )}
        </Card>

        {/* Source citations */}
        {sources?.length > 0 && !isUser && (
          <Collapse
            ghost
            size="small"
            items={[
              {
                key: 'sources',
                label: <Tag color="blue">📎 {sources.length} 个引用来源</Tag>,
                children: sources.map((s, i) => (
                  <div key={i} style={{ fontSize: 12, padding: '4px 0', borderBottom: '1px solid #f0f0f0' }}>
                    <strong>[{i + 1}]</strong> {s.doc_title}{' '}
                    {s.score != null && <Tag>{(s.score * 100).toFixed(1)}%</Tag>}
                  </div>
                )),
              },
            ]}
            style={{ marginTop: 6 }}
          />
        )}
      </div>
    </div>
  )
}

function Avatar(props: any) {
  return <div {...props} style={{ ...props.style, borderRadius: '50%', width: 36, height: 36, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontSize: 14 }} />
}
