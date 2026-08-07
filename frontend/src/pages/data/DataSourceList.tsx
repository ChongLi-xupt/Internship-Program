/** Data source list page */

import { useState, useEffect } from 'react'
import { Card, Button, Table, Tag, Space, Modal, Form, Input, Select, message } from 'antd'
import { PlusOutlined, DatabaseOutlined, ApiOutlined, CheckCircleOutlined, CloseCircleOutlined } from '@ant-design/icons'
import client from '../../api/client'

export default function DataSourceList() {
  const [data, setData] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [testingId, setTestingId] = useState<string | null>(null)
  const [form] = Form.useForm()

  async function load() {
    setLoading(true)
    try {
      const res = await client.get('/datasources')
      setData(res.data)
    } catch {}
    setLoading(false)
  }

  useEffect(() => { load() }, [])

  async function handleCreate(values: any) {
    try {
      await client.post('/datasources', values)
      message.success('数据源创建成功')
      setModalOpen(false)
      form.resetFields()
      load()
    } catch (err: any) {
      message.error(err.response?.data?.detail || '创建失败')
    }
  }

  async function testConnection(id: string) {
    setTestingId(id)
    try {
      const res = await client.post(`/datasources/${id}/test-connection`)
      if (res.data.success) {
        message.success(`连接成功 (${res.data.latency_ms}ms)`)
      } else {
        message.error(`连接失败: ${res.data.error}`)
      }
    } catch (err: any) {
      message.error(err.response?.data?.detail || '测试失败')
    }
    setTestingId(null)
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <h2 style={{ margin: 0 }}>💾 数据源管理</h2>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>
          新建数据源
        </Button>
      </div>

      <Table
        dataSource={data}
        loading={loading}
        rowKey="id"
        pagination={{ pageSize: 10 }}
        columns={[
          { title: '名称', dataIndex: 'name' },
          { title: '类型', dataIndex: 'db_type', render: (t: string) => <Tag>{t.toUpperCase()}</Tag> },
          {
            title: '状态',
            dataIndex: 'status',
            render: (s: string) =>
              s === 'active' ? (
                <Tag color="success" icon={<CheckCircleOutlined />}>正常</Tag>
              ) : (
                <Tag color="error" icon={<CloseCircleOutlined />}>{s}</Tag>
              ),
          },
          { title: '最大行数', dataIndex: 'max_rows_per_query', width: 100 },
          { title: '超时(秒)', dataIndex: 'query_timeout', width: 80 },
          {
            title: '操作',
            key: 'action',
            render: (_: any, record: any) => (
              <Space>
                <Button
                  size="small"
                  icon={<ApiOutlined />}
                  loading={testingId === record.id}
                  onClick={() => testConnection(record.id)}
                >
                  测试连接
                </Button>
              </Space>
            ),
          },
        ]}
      />

      <Modal
        title="新建数据源"
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        okText="保存"
        onOk={() => form.submit()}
      >
        <Form form={form} layout="vertical" onFinish={handleCreate}>
          <Form.Item name="name" label="名称" rules={[{ required: true }]}>
            <Input placeholder="如：生产数据库" />
          </Form.Item>
          <Form.Item name="db_type" label="数据库类型" rules={[{ required: true }]}>
            <Select options={[
              { value: 'postgresql', label: 'PostgreSQL' },
              { value: 'mysql', label: 'MySQL' },
              { value: 'clickhouse', label: 'ClickHouse' },
            ]} />
          </Form.Item>

          {/* Connection config sub-fields */}
          <Form.Item label="主机地址">
            <Input.Group compact>
              <Form.Item name={['connection_config', 'host']} noStyle rules={[{ required: true }]}>
                <Input placeholder="localhost" style={{ width: '55%' }} />
              </Form.Item>
              <Form.Item name={['connection_config', 'port']} noStyle rules={[{ required: true }]}>
                <Input type="number" placeholder="5432" style={{ width: '45%' }} />
              </Form.Item>
            </Input.Group>
          </Form.Item>

          <Form.Item name={['connection_config', 'database']} label="数据库名" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name={['connection_config', 'username']} label="用户名" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name={['connection_config', 'password']} label="密码" rules={[{ required: true }]}>
            <Input.Password />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
