/** Knowledge base list & management page */

import { useState, useEffect } from 'react'
import { Card, Button, Table, Tag, Space, Modal, Form, Input, Switch, Select, message, Upload } from 'antd'
import { PlusOutlined, FileTextOutlined, DeleteOutlined, SettingOutlined, UploadOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import client from '../../api/client'

const columns = [
  { title: '名称', dataIndex: 'name', key: 'name' },
  {
    title: '状态',
    dataIndex: 'status',
    key: 'status',
    render: (s: string) => {
      const map: Record<string, { color: string; text: string }> = {
        ready: { color: 'success', text: '就绪' },
        indexing: { color: 'processing', text: '索引中' },
        draft: { color: 'default', text: '草稿' },
        error: { color: 'error', text: '错误' },
      }
      const m = map[s] || { color: 'default', text: s }
      return <Tag color={m.color}>{m.text}</Tag>
    },
  },
  { title: '文档数', dataIndex: 'doc_count', key: 'doc_count', width: 80 },
  { title: '分片数', dataIndex: 'chunk_count', key: 'chunk_count', width: 80 },
  { title: 'Embedding模型', dataIndex: 'embedding_model', key: 'embedding_model' },
  { title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 170,
    render: (d: string) => new Date(d).toLocaleString('zh-CN'),
  },
]

export default function KnowledgeList() {
  const [data, setData] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [createModalOpen, setCreateModalOpen] = useState(false)
  const [form] = Form.useForm()
  const navigate = useNavigate()

  async function loadData() {
    setLoading(true)
    try {
      const res = await client.get('/knowledge-bases')
      setData(res.data)
    } catch {}
    setLoading(false)
  }

  useEffect(() => { loadData() }, [])

  async function handleCreate(values: any) {
    try {
      await client.post('/knowledge-bases', values)
      message.success('知识库创建成功')
      setCreateModalOpen(false)
      form.resetFields()
      loadData()
    } catch (err: any) {
      message.error(err.response?.data?.detail || '创建失败')
    }
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <h2 style={{ margin: 0 }}>📚 知识库管理</h2>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateModalOpen(true)}>
          新建知识库
        </Button>
      </div>

      <Table
        columns={columns}
        dataSource={data}
        rowKey="id"
        loading={loading}
        pagination={{ pageSize: 10 }}
        onRow={(record) => ({
          onClick: () => navigate(`/knowledge/${record.id}`),
          style: { cursor: 'pointer' },
        })}
      />

      <Modal
        title="新建知识库"
        open={createModalOpen}
        onCancel={() => setCreateModalOpen(false)}
        onOk={() => form.submit()}
        okText="创建"
        cancelText="取消"
      >
        <Form form={form} layout="vertical" onFinish={handleCreate}>
          <Form.Item name="name" label="名称" rules={[{ required: true }]}>
            <Input placeholder="例如：HR制度知识库" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={2} placeholder="知识库用途说明" />
          </Form.Item>
          <Form.Item name="embedding_model" label="Embedding 模型" initialValue="text-embedding-3-small">
            <Select options={[
              { value: 'text-embedding-3-small', label: 'text-embedding-3-small (推荐)' },
              { value: 'text-embedding-3-large', label: 'text-embedding-3-large' },
            ]} />
          </Form.Item>
          <Form.Item name="chunk_size" label="分块大小" initialValue={512}>
            <Input type="number" min={100} max={4096} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
