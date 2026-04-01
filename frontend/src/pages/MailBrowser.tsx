import { useEffect, useState } from 'react'
import {
  Alert,
  Button,
  Card,
  Col,
  Descriptions,
  Empty,
  Form,
  Input,
  List,
  Row,
  Select,
  Space,
  Table,
  Tabs,
  Tag,
  Typography,
  message,
} from 'antd'
import { ReloadOutlined, SaveOutlined } from '@ant-design/icons'
import { apiFetch } from '@/lib/utils'
import {
  fetchMailBrowserProfile,
  fetchMailDetail,
  fetchPurchaseMails,
  fetchPurchases,
  type LuckMailMessage,
  type LuckMailPurchase,
  type MailBrowserProfile,
  type MailDetail,
} from '@/lib/mailBrowser'

const { Text, Paragraph } = Typography

type ConfigFormValues = {
  luckmail_base_url: string
  luckmail_api_key: string
}

export default function MailBrowser() {
  const [configForm] = Form.useForm<ConfigFormValues>()
  const [profile, setProfile] = useState<MailBrowserProfile | null>(null)
  const [purchases, setPurchases] = useState<LuckMailPurchase[]>([])
  const [selectedPurchase, setSelectedPurchase] = useState<LuckMailPurchase | null>(null)
  const [mails, setMails] = useState<LuckMailMessage[]>([])
  const [selectedMailId, setSelectedMailId] = useState('')
  const [mailDetail, setMailDetail] = useState<MailDetail | null>(null)
  const [purchaseKeyword, setPurchaseKeyword] = useState('')
  const [disabledFilter, setDisabledFilter] = useState<number | undefined>(0)
  const [purchasePage, setPurchasePage] = useState(1)
  const [purchaseTotal, setPurchaseTotal] = useState(0)
  const [savingConfig, setSavingConfig] = useState(false)
  const [loadingProfile, setLoadingProfile] = useState(false)
  const [loadingPurchases, setLoadingPurchases] = useState(false)
  const [loadingMails, setLoadingMails] = useState(false)
  const [loadingDetail, setLoadingDetail] = useState(false)
  const pageSize = 20

  // 初始化时同时加载配置和当前账号概览。
  useEffect(() => {
    void initializePage()
  }, [])

  async function initializePage() {
    await loadConfig()
    await loadProfile(true)
    await loadPurchases(1, true)
  }

  async function loadConfig() {
    const config = await apiFetch('/config')
    configForm.setFieldsValue({
      luckmail_base_url: config.luckmail_base_url || 'https://mails.luckyous.com/',
      luckmail_api_key: config.luckmail_api_key || '',
    })
  }

  async function loadProfile(silent = false) {
    setLoadingProfile(true)
    try {
      const nextProfile = await fetchMailBrowserProfile()
      setProfile(nextProfile)
    } catch (error: any) {
      if (!silent) message.error(error.message || '读取 LuckMail 账号信息失败')
    } finally {
      setLoadingProfile(false)
    }
  }

  async function loadPurchases(
    page = purchasePage,
    silent = false,
    nextKeyword = purchaseKeyword,
    nextDisabled = disabledFilter
  ) {
    setLoadingPurchases(true)
    try {
      const result = await fetchPurchases({
        page,
        pageSize,
        keyword: nextKeyword.trim(),
        userDisabled: nextDisabled,
      })
      setPurchases(result.items)
      setPurchasePage(result.page)
      setPurchaseTotal(result.total)
    } catch (error: any) {
      setPurchases([])
      setPurchaseTotal(0)
      if (!silent) message.error(error.message || '读取已购邮箱失败')
    } finally {
      setLoadingPurchases(false)
    }
  }

  async function openPurchase(record: LuckMailPurchase) {
    setSelectedPurchase(record)
    setSelectedMailId('')
    setMailDetail(null)
    setLoadingMails(true)
    try {
      const result = await fetchPurchaseMails(record.token)
      setMails(result.mails || [])
    } catch (error: any) {
      setMails([])
      message.error(error.message || '读取邮件列表失败')
    } finally {
      setLoadingMails(false)
    }
  }

  async function openMail(mail: LuckMailMessage) {
    if (!selectedPurchase) return
    setSelectedMailId(mail.message_id)
    setLoadingDetail(true)
    try {
      const detail = await fetchMailDetail(selectedPurchase.token, mail.message_id)
      setMailDetail(detail)
    } catch (error: any) {
      setMailDetail(null)
      message.error(error.message || '读取邮件详情失败')
    } finally {
      setLoadingDetail(false)
    }
  }

  async function handleSaveConfig() {
    const values = await configForm.validateFields()
    setSavingConfig(true)
    try {
      await apiFetch('/config', {
        method: 'PUT',
        body: JSON.stringify({
          data: {
            luckmail_base_url: values.luckmail_base_url,
            luckmail_api_key: values.luckmail_api_key,
          },
        }),
      })
      message.success('LuckMail 配置已保存')
      setSelectedPurchase(null)
      setMails([])
      setSelectedMailId('')
      setMailDetail(null)
      await loadProfile()
      await loadPurchases(1)
    } catch (error: any) {
      message.error(error.message || '保存 LuckMail 配置失败')
    } finally {
      setSavingConfig(false)
    }
  }

  const purchaseColumns = [
    {
      title: '邮箱',
      dataIndex: 'email_address',
      key: 'email_address',
      render: (value: string) => <Text copyable={{ text: value }}>{value}</Text>,
    },
    {
      title: '项目',
      dataIndex: 'project_name',
      key: 'project_name',
      render: (value: string) => value || '-',
    },
    {
      title: '标签',
      dataIndex: 'tag_name',
      key: 'tag_name',
      render: (value: string) => (value ? <Tag color="blue">{value}</Tag> : '-'),
    },
    {
      title: '状态',
      key: 'status',
      render: (_: unknown, record: LuckMailPurchase) =>
        record.user_disabled ? <Tag color="red">已禁用</Tag> : <Tag color="green">可用</Tag>,
    },
  ]

  return (
    <div>
      <Card
        title="LuckMail 邮箱浏览"
        extra={
          <Space>
            <Button icon={<ReloadOutlined />} loading={loadingProfile} onClick={() => void loadProfile()}>
              刷新概览
            </Button>
            <Button type="primary" icon={<SaveOutlined />} loading={savingConfig} onClick={() => void handleSaveConfig()}>
              保存配置
            </Button>
          </Space>
        }
        style={{ marginBottom: 16 }}
      >
        <Form form={configForm} layout="vertical">
          <Row gutter={16}>
            <Col xs={24} lg={10}>
              <Form.Item
                name="luckmail_base_url"
                label="平台地址"
                rules={[{ required: true, message: '请输入 LuckMail 平台地址' }]}
              >
                <Input placeholder="https://mails.luckyous.com/" />
              </Form.Item>
            </Col>
            <Col xs={24} lg={14}>
              <Form.Item
                name="luckmail_api_key"
                label="API Key"
                rules={[{ required: true, message: '请输入 LuckMail API Key' }]}
              >
                <Input.Password placeholder="请输入 API Key" />
              </Form.Item>
            </Col>
          </Row>
        </Form>

        {!profile?.configured ? (
          <Alert
            type="warning"
            showIcon
            message="还没有可用的 LuckMail 配置"
            description="先在上面填好平台地址和 API Key，再保存并刷新邮箱列表。"
          />
        ) : (
          <Descriptions size="small" column={{ xs: 1, md: 2, xl: 4 }} bordered>
            <Descriptions.Item label="用户名">{profile.username || '-'}</Descriptions.Item>
            <Descriptions.Item label="登录邮箱">{profile.email || '-'}</Descriptions.Item>
            <Descriptions.Item label="余额">{profile.balance || '-'}</Descriptions.Item>
            <Descriptions.Item label="平台地址">{profile.base_url || '-'}</Descriptions.Item>
          </Descriptions>
        )}
      </Card>

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={11}>
          <Card
            title="已购邮箱"
            extra={
              <Space>
                <Input.Search
                  placeholder="搜索邮箱"
                  allowClear
                  style={{ width: 180 }}
                  onSearch={(value) => {
                    setPurchaseKeyword(value)
                    void loadPurchases(1, false, value, disabledFilter)
                  }}
                />
                <Select
                  value={disabledFilter}
                  style={{ width: 120 }}
                  options={[
                    { label: '可用邮箱', value: 0 },
                    { label: '已禁用', value: 1 },
                    { label: '全部', value: undefined },
                  ]}
                  onChange={(value) => {
                    setDisabledFilter(value)
                    void loadPurchases(1, false, purchaseKeyword, value)
                  }}
                />
              </Space>
            }
          >
            <Table
              rowKey="id"
              size="small"
              loading={loadingPurchases}
              columns={purchaseColumns}
              dataSource={purchases}
              pagination={{
                current: purchasePage,
                pageSize,
                total: purchaseTotal,
                onChange: (page) => void loadPurchases(page),
              }}
              onRow={(record) => ({
                onClick: () => void openPurchase(record),
              })}
              rowClassName={(record) => (record.id === selectedPurchase?.id ? 'ant-table-row-selected' : '')}
            />
          </Card>
        </Col>

        <Col xs={24} xl={13}>
          <Space direction="vertical" size={16} style={{ width: '100%' }}>
            <Card
              title={selectedPurchase ? `邮件列表: ${selectedPurchase.email_address}` : '邮件列表'}
              extra={
                selectedPurchase ? (
                  <Button icon={<ReloadOutlined />} loading={loadingMails} onClick={() => void openPurchase(selectedPurchase)}>
                    刷新邮件
                  </Button>
                ) : null
              }
            >
              {!selectedPurchase ? (
                <Empty description="先从左侧手动选择一个邮箱" />
              ) : (
                <List
                  loading={loadingMails}
                  locale={{ emptyText: '这个邮箱还没有邮件' }}
                  dataSource={mails}
                  renderItem={(item) => (
                    <List.Item
                      style={{
                        cursor: 'pointer',
                        borderRadius: 8,
                        padding: '12px 14px',
                        marginBottom: 8,
                        border: '1px solid rgba(5,5,5,0.06)',
                        background: item.message_id === selectedMailId ? 'rgba(22,119,255,0.08)' : 'transparent',
                      }}
                      onClick={() => void openMail(item)}
                    >
                      <List.Item.Meta
                        title={
                          <Space wrap>
                            <span>{item.subject || '无主题'}</span>
                            <Text type="secondary">{item.received_at || '-'}</Text>
                          </Space>
                        }
                        description={
                          <Paragraph type="secondary" ellipsis={{ rows: 2 }} style={{ marginBottom: 0 }}>
                            {(item.body || item.html_body || item.from_addr || '无预览内容').replace(/<[^>]+>/g, ' ')}
                          </Paragraph>
                        }
                      />
                    </List.Item>
                  )}
                />
              )}
            </Card>

            <Card title="邮件详情" loading={loadingDetail}>
              {!mailDetail ? (
                <Empty description="点击上方邮件后在这里查看正文" />
              ) : (
                <Space direction="vertical" size={16} style={{ width: '100%' }}>
                  <Descriptions size="small" column={1} bordered>
                    <Descriptions.Item label="发件人">{mailDetail.from_addr || '-'}</Descriptions.Item>
                    <Descriptions.Item label="收件人">{mailDetail.to || '-'}</Descriptions.Item>
                    <Descriptions.Item label="接收时间">{mailDetail.received_at || '-'}</Descriptions.Item>
                    <Descriptions.Item label="主题">{mailDetail.subject || '-'}</Descriptions.Item>
                    <Descriptions.Item label="验证码">
                      {mailDetail.verification_code ? <Tag color="green">{mailDetail.verification_code}</Tag> : '未识别'}
                    </Descriptions.Item>
                  </Descriptions>

                  <Tabs
                    items={[
                      {
                        key: 'text',
                        label: '文本内容',
                        children: (
                          <Paragraph style={{ whiteSpace: 'pre-wrap', marginBottom: 0 }}>
                            {mailDetail.body_text || '没有纯文本内容'}
                          </Paragraph>
                        ),
                      },
                      {
                        key: 'html',
                        label: 'HTML 预览',
                        children: mailDetail.body_html ? (
                          // 用 iframe 沙箱展示 HTML，避免邮件内容直接执行在主页面上下文里。
                          <iframe
                            title="mail-html-preview"
                            srcDoc={mailDetail.body_html}
                            sandbox=""
                            style={{ width: '100%', minHeight: 360, border: '1px solid #f0f0f0', borderRadius: 8 }}
                          />
                        ) : (
                          <Empty description="没有 HTML 内容" />
                        ),
                      },
                    ]}
                  />
                </Space>
              )}
            </Card>
          </Space>
        </Col>
      </Row>
    </div>
  )
}
