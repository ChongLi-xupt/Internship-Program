/** Knowledge base detail page with document upload */

import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Card,
  Button,
  Table,
  Tag,
  Space,
  Upload,
  message,
  Progress,
  Empty,
  Spin,
  Descriptions,
  Popconfirm,
} from 'antd'
import {
  UploadOutlined,
  DeleteOutlined,
  ArrowLeftOutlined,
  FileTextOutlined,
  ReloadOutlined,
} from '@ant-design/icons'
import client from '../../api/client'

interface Document {
  id: string
  filename: string
  status: string
  chunk_count: number
  created_at: string
  file_size?: number
}

export default function KnowledgeDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [kb, setKb] = useState<any>(null)
  const [documents, setDocuments] = useState<Document[]>([])
  const [loading, setLoading] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)

  useEffect(() => {
    if (id) {
      loadKnowledgeBase()
      loadDocuments()
    }
  }, [id])

  async function loadKnowledgeBase() {
    try {
      const res = await client.get(`/knowledge-bases/${id}`)
      setKb(res.data)
    } catch (err: any) {
      message.error('加载知识库信息失败')
    }
  }

  async function loadDocuments() {
    setLoading(true)
    try {
      const res = await client.get(`/knowledge-bases/${id}/documents`)
      setDocuments(res.data || [])
    } catch {}
    setLoading(false)
  }

  async function handleUpload(file: File) {
    const validTypes = [
      'application/pdf',
      'application/msword',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      'application/vnd.ms-excel',
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      'text/plain',
      'text/markdown',
    ]

    if (!validTypes.includes(file.type) && !file.name.match(/\.(pdf|doc|docx|xls|xlsx|txt|md)$/i)) {
      message.error('仅支持 PDF、Word、Excel、TXT、Markdown 格式')
      return false
    }

    setUploading(true)
    setUploadProgress(0)

    const formData = new FormData()
    formData.append('file', file)

    try {
      await client.post(`/knowledge-bases/${id}/documents`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        onUploadProgress: (e) => {
          if (e.total) {
            setUploadProgress(Math.round((e.loaded * 100) / e.total))
          }
        },
      })
      message.success(`${file.name} 上传成功，正在索引...`)
      loadDocuments()
    } catch (err: any) {
      message.error(err.response?.data?.detail || '上传失败')
    }

    setUploading(false)
    setUploadProgress(0)
    return false // 阻止默认上传行为
  }

  async function handleDelete(docId: string) {
    try {
      await client.delete(`/knowledge-bases/${id}/documents/${docId}`)
      message.success('文档已删除')
      loadDocuments()
    } catch (err: any) {
      message.error(err.response?.data?.detail || '删除失败')
    }
  }

  const statusMap: Record<string, { color: string; text: string }> = {
    pending: { color: 'default', text: '待处理' },
    parsing: { color: 'processing', text: '解析中' },
    indexing: { color: 'processing', text: '索引中' },
    ready: { color: 'success', text: '就绪' },
    error: { color: 'error', text: '错误' },
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Space>
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/knowledge')}>
            返回列表
          </Button>
          <h2 style={{ margin: 0 }}>📁 {kb?.name || '知识库详情'}</h2>
        </Space>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={() => { loadKnowledgeBase(); loadDocuments(); }}>
            刷新
          </Button>
        </Space>
      </div>

      {kb && (
        <Card size="small" style={{ marginBottom: 16 }}>
          <Descriptions size="small" column={4}>
            <Descriptions.Item label="描述">{kb.description || '-'}</Descriptions.Item>
            <Descriptions.Item label="文档数">{kb.doc_count || 0}</Descriptions.Item>
            <Descriptions.Item label="分片数">{kb.chunk_count || 0}</Descriptions.Item>
            <Descriptions.Item label="状态">
              <Tag color={kb.status === 'ready' ? 'success' : 'processing'}>
                {kb.status === 'ready' ? '就绪' : '索引中'}
              </Tag>
            </Descriptions.Item>
          </Descriptions>
        </Card>
      )}

      <Card
        title={
          <Space>
            <FileTextOutlined />
            <span>文档列表</span>
            <Tag color="blue">{documents.length} 个文档</Tag>
          </Space>
        }
        extra={
          <Space>
            <Upload
              accept=".pdf,.doc,.docx,.xls,.xlsx,.txt,.md"
              beforeUpload={handleUpload}
              showUploadList={false}
              multiple
            >
              <Button type="primary" icon={<UploadOutlined />} loading={uploading}>
                上传文档
              </Button>
            </Upload>
          </Space>
        }
      >
        {uploading && (
          <div style={{ marginBottom: 16 }}>
            <Progress percent={uploadProgress} status="active" />
          </div>
        )}

        {loading ? (
          <div style={{ textAlign: 'center', padding: 40 }}>
            <Spin />
          </div>
        ) : documents.length === 0 ? (
          <Empty
            description="暂无文档，请上传 PDF、Word、Excel、TXT 等文件"
            image={Empty.PRESENTED_IMAGE_SIMPLE}
          >
            <Upload
              accept=".pdf,.doc,.docx,.xls,.xlsx,.txt,.md"
              beforeUpload={handleUpload}
              showUploadList={false}
            >
              <Button type="primary" icon={<UploadOutlined />}>
                上传第一个文档
              </Button>
            </Upload>
          </Empty>
        ) : (
          <Table
            dataSource={documents}
            rowKey="id"
            size="small"
            pagination={{ pageSize: 10 }}
            columns={[
              {
                title: '文件名',
                dataIndex: 'filename',
                key: 'filename',
                render: (name: string) => (
                  <Space>
                    <FileTextOutlined />
                    <span>{name}</span>
                  </Space>
                ),
              },
              {
                title: '状态',
                dataIndex: 'status',
                key: 'status',
                width: 100,
                render: (status: string) => {
                  const s = statusMap[status] || { color: 'default', text: status }
                  return <Tag color={s.color}>{s.text}</Tag>
                },
              },
              {
                title: '分片数',
                dataIndex: 'chunk_count',
                key: 'chunk_count',
                width: 80,
              },
              {
                title: '上传时间',
                dataIndex: 'created_at',
                key: 'created_at',
                width: 170,
                render: (d: string) => new Date(d).toLocaleString('zh-CN'),
              },
              {
                title: '操作',
                key: 'action',
                width: 80,
                render: (_, record) => (
                  <Popconfirm
                    title="确定删除此文档？"
                    onConfirm={() => handleDelete(record.id)}
                    okText="删除"
                    cancelText="取消"
                  >
                    <Button type="link" danger icon={<DeleteOutlined />} size="small">
                      删除
                    </Button>
                  </Popconfirm>
                ),
              },
            ]}
          />
        )}
      </Card>
    </div>
  )
}