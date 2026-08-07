/** SQL Examples (Few-shot) management page */

import { useState, useEffect } from 'react'
import { Table, Button, Modal, Form, Input, Select, Space, message, Tag, Popconfirm } from 'antd'
import { PlusOutlined, CheckCircleOutlined } from '@ant-design/icons'
import client from '../../api/client'

export default function SqlExamples() {
  const [data, setData] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [form] = Form.useForm()

  async function load() {
    setLoading(true)
    try {
      const res = await client.get('/semantic/sql-examples')
      setData(res.data)
    } catch {}
    setLoading(false)
  }

  useEffect(() => { load() }, [])

  async function handleCreate(values: any) {
    try {
      await client.post('/semantic/sql-examples', values)
      message.success('示例添加成功')
      setModalOpen(false)
      form.resetFields()
      load()
    } catch (e: any) { message.error(e.response?.data?.detail || '操作失败') }
  }

  async function verify(id: string) {
    try {
      await client.post(`/semantic/sql-examples/${id}/verify`)
      message.success('已审核通过')
      load()
    } catch (e: any) { message.error(e.response?.data?.detail || '操作失败') }
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <h2 style={{ margin: 0 }}>📝 SQL 示例库（Few-shot）</h2>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>
          新增示例
        </Button>
      </div>

      <p style={{ color: '#666', marginBottom: 12 }}>
        SQL 示例用于提升 NL2SQL 的准确率。由提示词工程师编写、DBA 审核后生效。
        使用次数越多的示例会被优先匹配。
      </p>

      <Table
        dataSource={data}
        loading={loading}
        rowKey="id"
        pagination={{ pageSize: 15 }}
        columns={[
          {
            title: '问题',
            dataIndex: 'question',
            ellipsis: true,
            width: 280,
          },
          {
            title: 'SQL',
            dataIndex: 'sql',
            ellipsis: true,
            render: (sql: string) => (
              <code style={{
                background: '#f5f5f5',
                padding: '2px 6px',
                borderRadius: 4,
                fontSize: 12,
              }}>
                {sql.length > 60 ? sql.slice(0, 60) + '...' : sql}
              </code>
            ),
          },
          {
            title: '状态',
            dataIndex: 'verified',
            width: 90,
            render: (v: boolean) =>
              v ? <Tag color="success" icon={<CheckCircleOutlined />}>已审核</Tag> : <Tag>待审核</Tag>,
          },
          { title: '使用次数', dataIndex: 'usage_count', width: 90, sorter: (a: any, b: any) => a.usage_count - b.usage_count },
          {
            title: '操作',
            key: 'action',
            width: 100,
            render: (_: any, r: any) => (
              !r.verified && (
                <Popconfirm title="确认审核通过？" onConfirm={() => verify(r.id)}>
                  <Button size="small" type="link">审核通过</Button>
                </Popconfirm>
              )
            ),
          },
        ]}
      />

      <Modal
        title="新增 SQL 示例"
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={() => form.submit()}
        okText="保存"
        width={650}
      >
        <Form form={form} layout="vertical" onFinish={handleCreate}>
          <Form.Item name="question" label="自然语言问题" rules={[{ required: true }]}>
            <Input.TextArea rows={2} placeholder="用户可能会这样问..." />
          </Form.Item>
          <Form.Item name="sql" label="对应 SQL" rules={[{ required: true }]}>
            <Input.TextArea rows={4} placeholder="SELECT ..." style={{ fontFamily: 'monospace' }} />
          </Form.Item>
          <Form.Item name="explanation" label="说明">
            <Input.TextArea rows={2} placeholder="解释这条 SQL 的思路..." />
          </Form.Item>
          <Form.Item name="tags" label="标签">
            <Select mode="tags" placeholder="分类标签，如：销售、聚合、趋势" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
