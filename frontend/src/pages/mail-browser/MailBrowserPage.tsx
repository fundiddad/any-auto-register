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

const { Paragraph, Text } = Typography

type ConfigValues = {
  luckmail_base_url: string
  luckmail_api_key: string
}

export default function MailBrowserPage() {
  const [configForm] = Form.useForm<ConfigValues>()
  const [profile, setProfile] = useState<MailBrowserProfile | null>(null)
  const [purchases, setPurchases] = useState<LuckMailPurchase[]>([])
  const [selectedPurchase, setSelectedPurchase] = useState<LuckMailPurchase | null>(null)
  const [mails, setMails] = useState<LuckMailMessage[]>([])
  const [selectedMailId, setSelectedMailId] = useState('')
  const [mailDetail, setMailDetail] = useState<MailDetail | null>(null)
  const [keyword, setKeyword] = useState('')
  const [disabledFilter, setDisabledFilter] = useState<number | 'all'>(0)
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const [savingConfig, setSavingConfig] = useState(false)
  const [loadingProfile, setLoadingProfile] = useState(false)
  const [loadingPurchases, setLoadingPurchases] = useState(false)
  const [loadingMails, setLoadingMails] = useState(false)
  const [loadingDetail, setLoadingDetail] = useState(false)
  const pageSize = 20

  // Load current config and mailbox summary on first render.
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
      setProfile(await fetchMailBrowserProfile())
    } catch (error: any) {
      if (!silent) message.error(error.message || 'Failed to load LuckMail profile')
    } finally {
      setLoadingProfile(false)
    }
  }

  async function loadPurchases(
    nextPage = page,
    silent = false,
    nextKeyword = keyword,
    nextDisabled = disabledFilter
  ) {
    setLoadingPurchases(true)
    try {
      const result = await fetchPurchases({
        page: nextPage,
        pageSize,
        keyword: nextKeyword.trim(),
        userDisabled: nextDisabled === 'all' ? undefined : nextDisabled,
      })
      setPurchases(result.items)
      setPage(result.page)
      setTotal(result.total)
    } catch (error: any) {
      setPurchases([])
      setTotal(0)
      if (!silent) message.error(error.message || 'Failed to load mailboxes')
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
      message.error(error.message || 'Failed to load message list')
    } finally {
      setLoadingMails(false)
    }
  }

  async function openMail(mail: LuckMailMessage) {
    if (!selectedPurchase) return
    setSelectedMailId(mail.message_id)
    setLoadingDetail(true)
    try {
      setMailDetail(await fetchMailDetail(selectedPurchase.token, mail.message_id))
    } catch (error: any) {
      setMailDetail(null)
      message.error(error.message || 'Failed to load message detail')
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
      message.success('LuckMail config saved')
      setSelectedPurchase(null)
      setMails([])
      setSelectedMailId('')
      setMailDetail(null)
      await loadProfile()
      await loadPurchases(1)
    } catch (error: any) {
      message.error(error.message || 'Failed to save LuckMail config')
    } finally {
      setSavingConfig(false)
    }
  }

  const columns = [
    {
      title: 'Mailbox',
      dataIndex: 'email_address',
      key: 'email_address',
      render: (value: string) => <Text copyable={{ text: value }}>{value}</Text>,
    },
    {
      title: 'Project',
      dataIndex: 'project_name',
      key: 'project_name',
      render: (value: string) => value || '-',
    },
    {
      title: 'Tag',
      dataIndex: 'tag_name',
      key: 'tag_name',
      render: (value: string) => (value ? <Tag color="blue">{value}</Tag> : '-'),
    },
    {
      title: 'Status',
      key: 'status',
      render: (_: unknown, record: LuckMailPurchase) =>
        record.user_disabled ? <Tag color="red">Disabled</Tag> : <Tag color="green">Active</Tag>,
    },
  ]

  return (
    <div>
      <Card
        title="LuckMail Mail Browser"
        style={{ marginBottom: 16 }}
        extra={
          <Space>
            <Button icon={<ReloadOutlined />} loading={loadingProfile} onClick={() => void loadProfile()}>
              Refresh
            </Button>
            <Button type="primary" icon={<SaveOutlined />} loading={savingConfig} onClick={() => void handleSaveConfig()}>
              Save
            </Button>
          </Space>
        }
      >
        <Form form={configForm} layout="vertical">
          <Row gutter={16}>
            <Col xs={24} lg={10}>
              <Form.Item name="luckmail_base_url" label="Base URL" rules={[{ required: true }]}>
                <Input placeholder="https://mails.luckyous.com/" />
              </Form.Item>
            </Col>
            <Col xs={24} lg={14}>
              <Form.Item name="luckmail_api_key" label="API Key" rules={[{ required: true }]}>
                <Input.Password placeholder="Enter API Key" />
              </Form.Item>
            </Col>
          </Row>
        </Form>

        {!profile?.configured ? (
          <Alert
            type="warning"
            showIcon
            message="LuckMail is not configured"
            description="Save a valid base URL and API key, then reload the mailbox list."
          />
        ) : (
          <Descriptions size="small" bordered column={{ xs: 1, md: 2, xl: 4 }}>
            <Descriptions.Item label="Username">{profile.username || '-'}</Descriptions.Item>
            <Descriptions.Item label="Login Email">{profile.email || '-'}</Descriptions.Item>
            <Descriptions.Item label="Balance">{profile.balance || '-'}</Descriptions.Item>
            <Descriptions.Item label="Base URL">{profile.base_url || '-'}</Descriptions.Item>
          </Descriptions>
        )}
      </Card>

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={11}>
          <Card
            title="Purchased Mailboxes"
            extra={
              <Space>
                <Input.Search
                  placeholder="Search mailbox"
                  allowClear
                  style={{ width: 180 }}
                  onSearch={(value) => {
                    setKeyword(value)
                    void loadPurchases(1, false, value, disabledFilter)
                  }}
                />
                <Select
                  value={disabledFilter}
                  style={{ width: 120 }}
                  options={[
                    { label: 'Active', value: 0 },
                    { label: 'Disabled', value: 1 },
                    { label: 'All', value: 'all' },
                  ]}
                  onChange={(value) => {
                    setDisabledFilter(value)
                    void loadPurchases(1, false, keyword, value)
                  }}
                />
              </Space>
            }
          >
            <Table
              rowKey="id"
              size="small"
              loading={loadingPurchases}
              columns={columns}
              dataSource={purchases}
              pagination={{
                current: page,
                pageSize,
                total,
                onChange: (nextPage) => void loadPurchases(nextPage),
              }}
              rowClassName={(record) => (record.id === selectedPurchase?.id ? 'ant-table-row-selected' : '')}
              onRow={(record) => ({
                onClick: () => void openPurchase(record),
              })}
            />
          </Card>
        </Col>

        <Col xs={24} xl={13}>
          <Space direction="vertical" size={16} style={{ width: '100%' }}>
            <Card
              title={selectedPurchase ? `Messages: ${selectedPurchase.email_address}` : 'Messages'}
              extra={
                selectedPurchase ? (
                  <Button icon={<ReloadOutlined />} loading={loadingMails} onClick={() => void openPurchase(selectedPurchase)}>
                    Refresh
                  </Button>
                ) : null
              }
            >
              {!selectedPurchase ? (
                <Empty description="Select a mailbox from the left table first" />
              ) : (
                <List
                  loading={loadingMails}
                  locale={{ emptyText: 'No messages yet' }}
                  dataSource={mails}
                  renderItem={(item) => (
                    <List.Item
                      style={{
                        cursor: 'pointer',
                        marginBottom: 8,
                        padding: '12px 14px',
                        borderRadius: 8,
                        border: '1px solid rgba(5,5,5,0.06)',
                        background: item.message_id === selectedMailId ? 'rgba(22,119,255,0.08)' : 'transparent',
                      }}
                      onClick={() => void openMail(item)}
                    >
                      <List.Item.Meta
                        title={
                          <Space wrap>
                            <span>{item.subject || 'No subject'}</span>
                            <Text type="secondary">{item.received_at || '-'}</Text>
                          </Space>
                        }
                        description={
                          <Paragraph type="secondary" ellipsis={{ rows: 2 }} style={{ marginBottom: 0 }}>
                            {(item.body || item.html_body || item.from_addr || 'No preview').replace(/<[^>]+>/g, ' ')}
                          </Paragraph>
                        }
                      />
                    </List.Item>
                  )}
                />
              )}
            </Card>

            <Card title="Message Detail" loading={loadingDetail}>
              {!mailDetail ? (
                <Empty description="Open a message to inspect its content" />
              ) : (
                <Space direction="vertical" size={16} style={{ width: '100%' }}>
                  <Descriptions size="small" bordered column={1}>
                    <Descriptions.Item label="From">{mailDetail.from_addr || '-'}</Descriptions.Item>
                    <Descriptions.Item label="To">{mailDetail.to || '-'}</Descriptions.Item>
                    <Descriptions.Item label="Received At">{mailDetail.received_at || '-'}</Descriptions.Item>
                    <Descriptions.Item label="Subject">{mailDetail.subject || '-'}</Descriptions.Item>
                    <Descriptions.Item label="Verification Code">
                      {mailDetail.verification_code ? <Tag color="green">{mailDetail.verification_code}</Tag> : 'N/A'}
                    </Descriptions.Item>
                  </Descriptions>

                  <Tabs
                    items={[
                      {
                        key: 'text',
                        label: 'Text',
                        children: (
                          <Paragraph style={{ marginBottom: 0, whiteSpace: 'pre-wrap' }}>
                            {mailDetail.body_text || 'No plain text content'}
                          </Paragraph>
                        ),
                      },
                      {
                        key: 'html',
                        label: 'HTML',
                        children: mailDetail.body_html ? (
                          // Use an iframe sandbox so raw email HTML does not run in the app context.
                          <iframe
                            title="mail-html-preview"
                            srcDoc={mailDetail.body_html}
                            sandbox=""
                            style={{ width: '100%', minHeight: 360, border: '1px solid #f0f0f0', borderRadius: 8 }}
                          />
                        ) : (
                          <Empty description="No HTML content" />
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
