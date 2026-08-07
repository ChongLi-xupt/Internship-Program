import { Row, Col, Card, Statistic, Typography, Tag } from 'antd'
import {
  FileTextOutlined,
  DatabaseOutlined,
  MessageOutlined,
  BarChartOutlined,
  RocketOutlined,
} from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'

const { Title, Paragraph } = Typography

export default function Dashboard() {
  const navigate = useNavigate()

  const stats = [
    { title: '知识库', value: 3, icon: <FileTextOutlined />, color: '#1677ff', path: '/knowledge' },
    { title: '文档总数', value: 127, icon: <FileTextOutlined />, color: '#52c41a', path: '/knowledge' },
    { title: '数据源', value: 2, icon: <DatabaseOutlined />, color: '#faad14', path: '/data/datasources' },
    { title: '对话次数', value: 1847, icon: <MessageOutlined />, color: '#722ed1', path: '/chat/rag' },
    { title: '查询次数', value: 523, icon: <BarChartOutlined />, color: '#eb2f96', path: '/chat/query' },
  ]

  return (
    <div>
      <Title level={3}>📊 系统概览</Title>
      <Paragraph type="secondary">RAG 问答与智慧问数平台运行状态</Paragraph>

      <Row gutter={[16, 16]} style={{ marginTop: 24 }}>
        {stats.map((s) => (
          <Col xs={24} sm={12} lg={4} key={s.title}>
            <div
              role="button"
              tabIndex={0}
              onClick={() => navigate(s.path)}
              onKeyDown={(e) => { if (e.key === 'Enter') navigate(s.path) }}
              style={{ cursor: 'pointer', transition: 'box-shadow 0.2s' }}
              onMouseEnter={(e) => (e.currentTarget.style.boxShadow = '0 2px 8px rgba(0,0,0,0.15)')}
              onMouseLeave={(e) => (e.currentTarget.style.boxShadow = 'none')}
            >
              <Card size="small">
                <Statistic
                  title={s.title}
                  value={s.value}
                  prefix={<span style={{ color: s.color }}>{s.icon}</span>}
                  valueStyle={{ color: s.color }}
                />
              </Card>
            </div>
          </Col>
        ))}
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 24 }}>
        <Col xs={24} lg={12}>
          <Card
            title={
              <span>
                <RocketOutlined /> 快速开始
              </span>
            }
            extra={<Tag color="processing">引导</Tag>}
          >
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <div
                role="button"
                tabIndex={0}
                onClick={() => navigate('/chat/rag')}
                onKeyDown={(e) => { if (e.key === 'Enter') navigate('/chat/rag') }}
                style={{ cursor: 'pointer', transition: 'box-shadow 0.2s' }}
                onMouseEnter={(e) => (e.currentTarget.style.boxShadow = '0 2px 8px rgba(0,0,0,0.15)')}
                onMouseLeave={(e) => (e.currentTarget.style.boxShadow = 'none')}
              >
                <Card size="small">
                  <Title level={5}>📚 RAG 知识问答</Title>
                  <Paragraph>上传文档到知识库，基于文档内容进行智能问答，支持引用溯源。</Paragraph>
                  <Tag color="blue">上传文档 → 建立索引 → 开始问答</Tag>
                </Card>
              </div>

              <div
                role="button"
                tabIndex={0}
                onClick={() => navigate('/chat/query')}
                onKeyDown={(e) => { if (e.key === 'Enter') navigate('/chat/query') }}
                style={{ cursor: 'pointer', transition: 'box-shadow 0.2s' }}
                onMouseEnter={(e) => (e.currentTarget.style.boxShadow = '0 2px 8px rgba(0,0,0,0.15)')}
                onMouseLeave={(e) => (e.currentTarget.style.boxShadow = 'none')}
              >
                <Card size="small">
                  <Title level={5}>📊 智慧问数</Title>
                  <Paragraph>用自然语言查询数据库，自动生成 SQL、执行查询、分析结果、生成图表。</Paragraph>
                  <Tag color="green">配置数据源 → 定义语义层 → 自然语言查数</Tag>
                </Card>
              </div>

              <div
                role="button"
                tabIndex={0}
                onClick={() => navigate('/knowledge')}
                onKeyDown={(e) => { if (e.key === 'Enter') navigate('/knowledge') }}
                style={{ cursor: 'pointer', transition: 'box-shadow 0.2s' }}
                onMouseEnter={(e) => (e.currentTarget.style.boxShadow = '0 2px 8px rgba(0,0,0,0.15)')}
                onMouseLeave={(e) => (e.currentTarget.style.boxShadow = 'none')}
              >
                <Card size="small">
                  <Title level={5}>📁 知识库管理</Title>
                  <Paragraph>创建知识库、上传 PDF/Word/Excel 等文档，管理向量索引。</Paragraph>
                  <Tag color="cyan">新建知识库 → 导入文档 → 自动切片</Tag>
                </Card>
              </div>
            </div>
          </Card>
        </Col>

        <Col xs={24} lg={12}>
          <Card title="🔧 系统信息">
            <Row gutter={[12, 12]}>
              <Col span={12}>
                <Statistic title="后端状态" value="运行中" valueStyle={{ color: '#52c41a' }} />
              </Col>
              <Col span={12}>
                <Statistic title="向量库" value="Qdrant" />
              </Col>
              <Col span={12}>
                <Statistic title="LLM 提供商" value="DeepSeek" />
              </Col>
              <Col span={12}>
                <Statistic title="Embedding" value="BGE-M3 (本地)" />
              </Col>
            </Row>
          </Card>
        </Col>
      </Row>
    </div>
  )
}
