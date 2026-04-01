import { apiFetch } from './utils'

// 这里集中放邮箱浏览页需要的类型和请求函数，避免页面文件过长。
export type MailBrowserProfile = {
  configured: boolean
  base_url: string
  username: string
  email: string
  balance: string
  status?: number
}

export type LuckMailPurchase = {
  id: number
  email_address: string
  token: string
  project_name: string
  price: string
  status: number
  tag_id: number
  tag_name: string
  user_disabled: number
  warranty_hours: number
  warranty_until?: string | null
  created_at?: string | null
}

export type PurchaseResponse = {
  items: LuckMailPurchase[]
  total: number
  page: number
  page_size: number
}

export type LuckMailMessage = {
  message_id: string
  from_addr: string
  subject: string
  body: string
  html_body: string
  received_at: string
}

export type MailListResponse = {
  email_address: string
  project: string
  warranty_until: string
  mails: LuckMailMessage[]
}

export type MailDetail = {
  message_id: string
  from_addr: string
  to: string
  subject: string
  body_text: string
  body_html: string
  received_at: string
  verification_code: string
}

export async function fetchMailBrowserProfile() {
  return apiFetch('/mail-browser/profile') as Promise<MailBrowserProfile>
}

export async function fetchPurchases(params: {
  page: number
  pageSize: number
  keyword?: string
  userDisabled?: number
}) {
  const search = new URLSearchParams({
    page: String(params.page),
    page_size: String(params.pageSize),
  })
  if (params.keyword) search.set('keyword', params.keyword)
  if (params.userDisabled !== undefined) {
    search.set('user_disabled', String(params.userDisabled))
  }
  return apiFetch(`/mail-browser/purchases?${search.toString()}`) as Promise<PurchaseResponse>
}

export async function fetchPurchaseMails(token: string) {
  const search = new URLSearchParams({ token })
  return apiFetch(`/mail-browser/mails?${search.toString()}`) as Promise<MailListResponse>
}

export async function fetchMailDetail(token: string, messageId: string) {
  const search = new URLSearchParams({ token, message_id: messageId })
  return apiFetch(`/mail-browser/mail-detail?${search.toString()}`) as Promise<MailDetail>
}
