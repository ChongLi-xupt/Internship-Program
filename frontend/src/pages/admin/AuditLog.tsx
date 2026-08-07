/** Audit log viewer */

import { useState, useEffect } from 'react'
import { Table, DatePicker, Select, Input, Space, Card } from 'antd'
import client from '../../api/client'

const { RangePicker } = DatePicker

export default function AuditLog() {
  const [data, setData] = useState<any[]>([])
  const [loading, setLoading] = useState(false)

  async function load(params?: any) {
    setLoading(true)
    try {
      const res = await client.get('/admin/audit-logs', { params })
      setData(res.data)
    } catch {}
    setLoading(false)
  }

  useEffect(() => { load() }, [])

  return (
    <div>
      <h2 style={{ marginBottom: 16 }}>📋 审计日志</h2>

      <Card size="small" style={{ marginBottom: 12 }}>
        <Space wrap>
          <Input.Search placeholder="搜索操作类型..." allowClear style={{ width: 200 }} onSearch={(v) => load({ action: v })} />
          <RangePicker onChange={(_, dates) => load({ start_date: dates[0], end_date: dates[1] })} />
        </Space>
      </Card>

      <Table
        dataSource={data}
        loading={loading}
        rowKey="id"
        pagination={{ pageSize: 30 }}
        size="small"
        scroll={{ x: 800 }}
        columns={[
          { title: '时间', dataIndex: 'created_at', width: 170,
            render: (d: string) => new Date(d).toLocaleString('zh-CN'),
          },
          { title: '操作', dataIndex: 'action', width: 140 },
          { title: '资源类型', dataIndex: 'resource_type', width: 120 },
          { title: 'IP 地址', dataIndex: 'ip_address', width: 140 },
          {
            title: '详情',
            dataIndex: 'detail',
            ellipsis: true,
            render: (d: any) => (
              <pre style={{ margin: 0, fontSize: 11, whiteSpace: 'pre-wrap' }}>
                {JSON.stringify(d, null, 2)?.slice(0, 100)}
              </pre>
            ),
          },
        ]}
      />
    </div>
  )
}
