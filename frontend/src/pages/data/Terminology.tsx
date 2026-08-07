/** Terminology management page */

import { useState, useEffect } from 'react'
import { Table, Button, Modal, Form, Input, Space, message, Tag, Select } from 'antd'
import { PlusOutlined, ImportOutlined } from '@ant-design/icons'
import client from '../../api/client'

export default function Terminology() {
  const [data, setData] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [form] = Form.useForm()

  async function load(q?: string) {
    setLoading(true)
    try {
      const params: any = {}
      if (q) params.q = q
      const res = await client.get('/semantic/terminology', { params })
      setData(res.data)
    } catch {}
    setLoading(false)
  }

  useEffect(() => { load() }, [])

  async function handleCreate(values: any) {
    try {
      await client.post('/semantic/terminology', values)
      message.success('术语添加成功')
      setModalOpen(false)
      form.resetFields()
      load()
    } catch (e: any) { message.error(e.response?.data?.detail || '操作失败') }
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <h2 style={{ margin: 0 }}>📖 术语库管理</h2>
        <Space>
          <Button icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>新增术语</Button>
        </Space>
      </div>

      <Table
        dataSource={data}
        loading={loading}
        rowKey="id"
        pagination={{ pageSize: 20 }}
        size="small"
        columns={[
          { title: '标准术语', dataIndex: 'term', width: 150 },
          {
            title: '同义词',
            dataIndex: 'synonyms',
            width: 200,
            render: (syns: string[]) => syns.map((s) => <Tag key={s}>{s}</Tag>),
          },
          { title: '定义', dataIndex: 'definition', ellipsis: true },
          { title: '领域', dataIndex: 'domain', width: 120 },
        ]}
      />

      <Modal title="新增术语" open={modalOpen} onCancel={() => setModalOpen(false)} onOk={() => form.submit()} okText="保存">
        <Form form={form} layout="vertical" onFinish={handleCreate}>
          <Form.Item name="term" label="标准术语" rules={[{ required: true }]}>
            <Input placeholder="如：GMV" />
          </Form.Item>
          <Form.Item name="synonyms" label="同义词">
            <Select mode="tags" tokenSeparators={[',', '，', ' ']} placeholder="输入后按回车添加" />
          </Form.Item>
          <Form.Item name="definition" label="定义">
            <Input.TextArea rows={2} />
          </Form.Item>
          <Form.Item name="domain" label="领域">
            <Input placeholder="如：电商、财务、HR" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
