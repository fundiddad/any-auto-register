import { BrowserRouter, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { Button, ConfigProvider, Layout, Menu } from 'antd'
import {
  DashboardOutlined,
  GlobalOutlined,
  HistoryOutlined,
  MailOutlined,
  MoonOutlined,
  SettingOutlined,
  SunOutlined,
  UserOutlined,
} from '@ant-design/icons'
import zhCN from 'antd/locale/zh_CN'
import Dashboard from '@/pages/Dashboard'
import Accounts from '@/pages/Accounts'
import Register from '@/pages/Register'
import Proxies from '@/pages/Proxies'
import Settings from '@/pages/Settings'
import TaskHistory from '@/pages/TaskHistory'
import MailBrowser from '@/pages/MailBrowser'
import { darkTheme, lightTheme } from './theme'

const { Content, Sider } = Layout

function AppShellContent() {
  const [themeMode, setThemeMode] = useState<'dark' | 'light'>(() =>
    (localStorage.getItem('theme') as 'dark' | 'light') || 'dark'
  )
  const [collapsed, setCollapsed] = useState(false)
  const [platforms, setPlatforms] = useState<{ key: string; label: string }[]>([])
  const location = useLocation()
  const navigate = useNavigate()

  useEffect(() => {
    document.documentElement.classList.toggle('light', themeMode === 'light')
    document.documentElement.style.setProperty(
      '--sider-trigger-border',
      themeMode === 'light' ? 'rgba(0,0,0,0.1)' : 'rgba(255,255,255,0.15)'
    )
    localStorage.setItem('theme', themeMode)
  }, [themeMode])

  useEffect(() => {
    fetch('/api/platforms')
      .then((response) => response.json())
      .then((data) =>
        setPlatforms(
          (data || [])
            .filter((item: any) => !['tavily', 'cursor'].includes(item.name))
            .map((item: any) => ({ key: item.name, label: item.display_name }))
        )
      )
  }, [])

  const currentTheme = themeMode === 'light' ? lightTheme : darkTheme
  const selectedKey = (() => {
    const path = location.pathname
    if (path === '/') return ['/']
    if (path.startsWith('/accounts')) return [path]
    if (path === '/history') return ['/history']
    if (path === '/proxies') return ['/proxies']
    if (path === '/mail-browser') return ['/mail-browser']
    if (path === '/settings') return ['/settings']
    return ['/']
  })()

  // 新页面直接挂进主导航，保持和现有后台同一套入口。
  const menuItems = [
    { key: '/', icon: <DashboardOutlined />, label: '仪表盘' },
    {
      key: '/accounts',
      icon: <UserOutlined />,
      label: '平台管理',
      children: platforms.map((item) => ({
        key: `/accounts/${item.key}`,
        label: item.label,
      })),
    },
    { key: '/history', icon: <HistoryOutlined />, label: '任务历史' },
    { key: '/proxies', icon: <GlobalOutlined />, label: '代理管理' },
    { key: '/mail-browser', icon: <MailOutlined />, label: '邮箱浏览' },
    { key: '/settings', icon: <SettingOutlined />, label: '全局配置' },
  ]

  return (
    <ConfigProvider theme={currentTheme} locale={zhCN}>
      <Layout style={{ minHeight: '100vh' }}>
        <Sider
          collapsible
          collapsed={collapsed}
          onCollapse={setCollapsed}
          width={220}
          style={{
            background: currentTheme.token?.colorBgContainer,
            borderRight: `1px solid ${currentTheme.token?.colorBorder}`,
          }}
        >
          <div
            style={{
              height: 64,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              borderBottom: `1px solid ${currentTheme.token?.colorBorder}`,
            }}
          >
            <DashboardOutlined style={{ fontSize: 20, color: currentTheme.token?.colorPrimary }} />
            {!collapsed && (
              <span
                style={{
                  marginLeft: 8,
                  fontWeight: 600,
                  fontSize: 14,
                  color: currentTheme.token?.colorText,
                }}
              >
                Account Manager
              </span>
            )}
          </div>

          <Menu
            mode="inline"
            selectedKeys={selectedKey}
            defaultOpenKeys={['/accounts']}
            items={menuItems}
            onClick={({ key }) => navigate(key)}
            style={{ borderRight: 0, background: 'transparent' }}
          />

          <div
            style={{
              position: 'absolute',
              bottom: 16,
              left: 0,
              right: 0,
              padding: '0 16px',
            }}
          >
            <Button
              block
              icon={themeMode === 'light' ? <SunOutlined /> : <MoonOutlined />}
              onClick={() => setThemeMode(themeMode === 'light' ? 'dark' : 'light')}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: collapsed ? 'center' : 'space-between',
              }}
            >
              {!collapsed && (themeMode === 'light' ? '亮色模式' : '暗色模式')}
            </Button>
          </div>
        </Sider>

        <Content
          style={{
            padding: 24,
            overflow: 'auto',
            background: currentTheme.token?.colorBgLayout,
          }}
        >
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/accounts" element={<Accounts />} />
            <Route path="/accounts/:platform" element={<Accounts />} />
            <Route path="/register" element={<Register />} />
            <Route path="/history" element={<TaskHistory />} />
            <Route path="/proxies" element={<Proxies />} />
            <Route path="/mail-browser" element={<MailBrowser />} />
            <Route path="/settings" element={<Settings />} />
          </Routes>
        </Content>
      </Layout>
    </ConfigProvider>
  )
}

export default function AppShell() {
  return (
    <BrowserRouter>
      <AppShellContent />
    </BrowserRouter>
  )
}
