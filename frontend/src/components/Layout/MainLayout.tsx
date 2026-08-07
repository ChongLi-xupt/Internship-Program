import { useState, Suspense } from 'react'
import { Layout } from 'antd'
import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import {
  DatabaseOutlined,
  FileTextOutlined,
  MessageOutlined,
  BarChartOutlined,
  SettingOutlined,
  LogoutOutlined,
  DashboardOutlined,
} from '@ant-design/icons'
import SiderNav from './SiderNav'

const { Content } = Layout

const menuItems = [
  { key: '/', icon: <DashboardOutlined />, label: '仪表盘' },
  { key: '/knowledge', icon: <FileTextOutlined />, label: '知识库' },
  { key: '/chat/rag', icon: <MessageOutlined />, label: 'RAG问答' },
  { key: '/chat/query', icon: <BarChartOutlined />, label: '智慧问数' },
  { type: 'divider' as const },
  { key: '/data/datasources', icon: <DatabaseOutlined />, label: '数据源' },
  { key: '/data/terminology', icon: <SettingOutlined />, label: '术语库' },
  { key: '/data/sql-examples', icon: <FileTextOutlined />, label: 'SQL示例' },
  { type: 'divider' as const },
  { key: '/admin/audit-logs', icon: <SettingOutlined />, label: '审计日志' },
]

export default function MainLayout() {
  const [collapsed, setCollapsed] = useState(false)
  const navigate = useNavigate()
  const location = useLocation()

  const siderWidth = collapsed ? 80 : 240

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <SiderNav
        collapsed={collapsed}
        onCollapse={setCollapsed}
        menuItems={menuItems}
        selectedKey={location.pathname}
        onMenuClick={(key) => navigate(key)}
        onLogout={() => {
          localStorage.removeItem('access_token')
          window.location.href = '/login'
        }}
      />
      <Layout style={{ marginLeft: siderWidth, transition: 'margin-left 0.2s' }}>
        <Content style={{ margin: 16, overflow: 'auto' }}>
          <Suspense fallback={<div style={{ padding: 40, textAlign: 'center' }}>加载中...</div>}>
            <Outlet />
          </Suspense>
        </Content>
      </Layout>
    </Layout>
  )
}
