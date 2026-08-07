import { Layout, Menu, Avatar, Dropdown } from 'antd'
import { UserOutlined, LogoutOutlined } from '@ant-design/icons'
import type { MenuProps } from 'antd'

const { Sider } = Layout

interface SiderNavProps {
  collapsed: boolean
  onCollapse: (collapsed: boolean) => void
  menuItems: any[]
  selectedKey: string
  onMenuClick: (key: string) => void
  onLogout: () => void
}

export default function SiderNav({ collapsed, onCollapse, menuItems, selectedKey, onMenuClick, onLogout }: SiderNavProps) {
  const userMenuItems: MenuProps['items'] = [
    { key: 'profile', icon: <UserOutlined />, label: '个人信息' },
    { type: 'divider' },
    { key: 'logout', icon: <LogoutOutlined />, label: '退出登录', danger: true },
  ]

  const handleSelect: MenuProps['onSelect'] = ({ key }) => {
    onMenuClick(String(key))
  }

  return (
    <Sider
      collapsible
      collapsed={collapsed}
      onCollapse={onCollapse}
      width={240}
      style={{
        height: '100vh',
        position: 'fixed',
        left: 0,
        top: 0,
        bottom: 0,
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
      }}
    >
      <div
        style={{
          height: 64,
          flexShrink: 0,
          display: 'flex',
          alignItems: 'center',
          justifyContent: collapsed ? 'center' : 'flex-start',
          padding: collapsed ? 0 : '0 20px',
          borderBottom: '1px solid rgba(255,255,255,0.1)',
        }}
      >
        {!collapsed && (
          <span style={{ color: '#fff', fontSize: 18, fontWeight: 700 }}>
            🧠 RAG 智慧问数
          </span>
        )}
        {collapsed && <span style={{ fontSize: 20 }}>🧠</span>}
      </div>

      <Menu
        theme="dark"
        mode="inline"
        selectedKeys={[selectedKey]}
        items={menuItems.filter((i) => i.type !== 'divider')}
        onClick={({ key }) => onMenuClick(String(key))}
        onSelect={handleSelect}
        style={{
          borderRight: 0,
          flex: 1,
          overflowY: 'auto',
          paddingBottom: 80,
        }}
      />

      <div
        style={{
          flexShrink: 0,
          width: '100%',
          padding: '12px 16px',
          borderTop: '1px solid rgba(255,255,255,0.1)',
        }}
      >
        <Dropdown menu={{ items: userMenuItems, onClick: ({ key }) => key === 'logout' && onLogout() }} placement="topRight">
          <div style={{ cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8 }}>
            <Avatar size="small" icon={<UserOutlined />} style={{ backgroundColor: '#1677ff' }} />
            {!collapsed && <span style={{ color: '#fff', fontSize: 13 }}>管理员</span>}
          </div>
        </Dropdown>
      </div>
    </Sider>
  )
}
