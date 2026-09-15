// Pro Tred admin panel — backend API client + types

export interface AccountInfo {
  login: number
  server: string
  broker: string
  currency: string
  balance: number
  equity: number
  margin: number
  free_margin: number
  margin_level: number
  leverage: number
  profit: number
  drawdown: number
}

export interface RiskSettings {
  risk_level: string
  risk_band: [number, number]
  risk_percent_per_trade: number
  max_risk_per_trade: number
  max_daily_drawdown: number
  daily_profit_target: number
  max_open_positions: number
  max_daily_trades: number
  min_confidence: number
  paper_trading: boolean
  scalping: boolean
  news_trading: boolean
  current_drawdown_pct: number
  current_drawdown_abs: number
  daily_profit_pct: number
  trades_today: number
}

export interface Position {
  ticket: number
  symbol: string
  direction: 'BUY' | 'SELL'
  volume: number
  entry: number
  sl: number
  tp: number
  current: number
  profit: number
  magic: number
  time: number
}

export interface Realized {
  currency: string
  today: number
  today_pct: number
  week: number
  week_pct: number
  month: number
  month_pct: number
  total: number
  total_pct: number
}

export interface Signal {
  id: number
  symbol: string
  direction: 'BUY' | 'SELL'
  entry: number
  stop_loss: number
  take_profit: number
  confidence: number
  timeframe: string
  reasons: string[]
  regime: string
  applied: boolean
  created_at: string
}

export interface TradeRow {
  ticket: number
  symbol: string
  direction: 'BUY' | 'SELL'
  volume: number
  entry: number
  sl: number | null
  tp: number | null
  current: number | null
  pnl: number | null
  pnl_pct: number | null
  status: 'open' | 'closed'
  opened_at: string
  closed_at: string | null
  close_reason: string | null
}

export interface EventRow {
  ts: string
  level: string
  source: string
  message: string
}

export interface AccountRow {
  id: number
  name: string
  link_code: string
  linked: boolean
  tg_username: string
  created_at: string
  linked_at: string
}

// ---------- admin / members analytics ----------
export interface AdminStats {
  users: {
    total: number
    web: number
    telegram: number
    active_today: number
    new_today: number
    active: number
  }
  instruments: {
    users_with_trades: number
    total_volume: number
    total_trades: number
    by_symbol: { symbol: string; count: number; volume: number; pnl: number; buys: number; sells: number }[]
  }
  accounts_total: number
  top_active: {
    id: number
    username: string | null
    name: string
    source: string
    plan: string
    login_count: number
    visits: number
    last_active_at: string
    created_at: string
  }[]
  pnl: {
    realized: number
    unrealized: number
    total_trades: number
    open_count: number
    wins: number
    losses: number
    winrate: number
  }
  pnl_history: { date: string; pnl: number; trades: number }[]
  live: {
    balance: number
    equity: number
    currency: string
    open_positions: number
    connected: boolean
  }
}

export interface AdminUser {
  id: number
  username: string | null
  name: string
  phone: string
  source: 'web' | 'telegram'
  plan: string
  active: boolean
  tg_username: string | null
  broker_connected: boolean
  trading_enabled: boolean
  paper_trading: boolean
  risk_level: string
  created_at: string
  last_active_at: string
  trade_count: number
  trade_volume: number
  realized_pnl: number
}

export interface DaySeries {
  date: string
  web?: number
  telegram?: number
  total?: number
  active?: number
}

export interface BroadcastRow {
  id: number
  text: string
  recipients: number
  created_at: string
}

export type Status = {
  connected: boolean
  account: AccountInfo | null
  risk: RiskSettings
  unrealized: { unrealized_pnl: number; unrealized_pnl_pct: number; open_count: number; positions: Position[] }
  realized: Realized
  signals: Record<string, string>
  ts: string
}

const ADMIN_TOKEN_KEY = 'pro_tred_admin_token'
const USER_TOKEN_KEY = 'pro_tred_user_token'
const USER_ROLE_KEY = 'pro_tred_user_role'

export const getToken = () => localStorage.getItem(ADMIN_TOKEN_KEY) || ''
export const setToken = (t: string) => localStorage.setItem(ADMIN_TOKEN_KEY, t)
export const getUserToken = () => localStorage.getItem(USER_TOKEN_KEY) || ''
export const setUserToken = (t: string) => localStorage.setItem(USER_TOKEN_KEY, t)
export const getUserRole = () => localStorage.getItem(USER_ROLE_KEY) || ''
export const setUserRole = (r: string) => localStorage.setItem(USER_ROLE_KEY, r)
export const clearAuth = () => {
  localStorage.removeItem(ADMIN_TOKEN_KEY)
  localStorage.removeItem(USER_TOKEN_KEY)
  localStorage.removeItem(USER_ROLE_KEY)
}

async function fetchJSON<T>(path: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  // admin yoki user token
  const adminToken = getToken()
  const userToken = getUserToken()
  if (adminToken) headers['X-Admin-Token'] = adminToken
  if (userToken) headers['X-User-Token'] = userToken
  const url = path.startsWith('http') ? path : `/api${path}`
  const res = await fetch(url, { ...init, headers: { ...headers, ...(init?.headers || {}) } })
  if (!res.ok) {
    let msg = `${res.status} ${res.statusText}`
    try {
      const body = await res.json()
      if (body.detail) msg = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
    } catch { /* noop */ }
    throw new Error(msg)
  }
  return res.json() as Promise<T>
}

export const api = {
  // auth
  adminLogin: (username: string, password: string) => fetchJSON<{ ok: boolean; token: string; username: string; role: string; user: any }>('/admin/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  }),
  login: (username: string, password: string) => fetchJSON<{ ok: boolean; role: string; user: any }>('/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  }),
  register: (username: string, name: string, password: string) => fetchJSON<{ ok: boolean; user: any }>('/register', {
    method: 'POST',
    body: JSON.stringify({ username, name, password }),
  }),
  me: () => fetchJSON<{ user: any; account: any }>('/me'),
  // user broker & trading
  connectBroker: (login: string, password: string, server: string) => fetchJSON<{ ok: boolean; message: string }>('/me/broker', {
    method: 'POST',
    body: JSON.stringify({ login, password, server }),
  }),
  getBroker: () => fetchJSON<{ connected: boolean; login?: string; server?: string; trading_enabled?: boolean; paper_trading?: boolean }>('/me/broker'),
  toggleTrading: () => fetchJSON<{ ok: boolean; trading_enabled: boolean }>('/me/trading', { method: 'POST' }),
  userSettings: (body: { risk_level?: string; paper_trading?: boolean; max_risk_pct?: number }) => fetchJSON<{ ok: boolean }>('/me/settings', {
    method: 'POST',
    body: JSON.stringify(body),
  }),
  myTrades: (limit = 50) => fetchJSON<{ trades: TradeRow[] }>(`/me/trades?limit=${limit}`),
  myPnl: () => fetchJSON<{ realized: number; unrealized: number; total_trades: number; wins: number; losses: number; winrate: number }>('/me/pnl'),
  closeMyTrade: (ticket: number) => fetchJSON<{ ok: boolean; error?: string; pnl?: number }>(`/me/trades/${ticket}/close`, { method: 'POST' }),
  myPnlHistory: (days = 14) => fetchJSON<{ series: { date: string; pnl: number; trades: number }[] }>(`/me/pnl/history?days=${days}`),
  mt5Accounts: () => fetchJSON<{ accounts: { login: number; server: string; leverage: number; currency: string }[]; error?: string }>('/mt5/accounts'),
  newsEvents: () => fetchJSON<{ events: any[]; now_ms: number }>('/news/events'),
  // admin
  status: () => fetchJSON<Status>('/status'),
  signals: (limit = 100) => fetchJSON<{ signals: Signal[] }>(`/signals?limit=${limit}`),
  trades: (onlyOpen = false) => fetchJSON<{ trades: TradeRow[] }>(`/trades?only_open=${onlyOpen}`),
  events: (limit = 100) => fetchJSON<{ events: EventRow[] }>(`/events?limit=${limit}`),
  settings: () => fetchJSON<RiskSettings>('/settings'),
  accounts: () => fetchJSON<{ accounts: AccountRow[] }>('/accounts'),
  createAccount: (name: string) => fetchJSON<{ ok: boolean; account: AccountRow; hint: string }>('/accounts', {
    method: 'POST',
    body: JSON.stringify({ name }),
  }),
  updateSettings: (body: Record<string, unknown>) => fetchJSON<{ ok: boolean; settings: RiskSettings; updated: Record<string, unknown> }>('/settings', {
    method: 'POST',
    body: JSON.stringify(body),
  }),
  closePosition: (ticket: number) => fetchJSON<{ ok: boolean; error?: string }>(`/positions/${ticket}/close`, { method: 'POST' }),
  telegramTest: (text: string) => fetchJSON<{ ok: boolean; sent_to: string[] }>(`/telegram/test?text=${encodeURIComponent(text)}`, { method: 'POST' }),
  sendReport: () => fetchJSON<{ ok: boolean }>('/report', { method: 'POST' }),
  adminStats: () => fetchJSON<AdminStats>('/admin/stats'),
  adminUsers: (source = '', q = '') => fetchJSON<{ users: AdminUser[] }>(`/admin/users?source=${encodeURIComponent(source)}&q=${encodeURIComponent(q)}`),
  adminRegistrations: (days = 14) => fetchJSON<{ series: DaySeries[] }>(`/admin/registrations?days=${days}`),
  adminDau: (days = 14) => fetchJSON<{ series: DaySeries[] }>(`/admin/dau?days=${days}`),
  adminBroadcasts: () => fetchJSON<{ broadcasts: BroadcastRow[] }>('/admin/broadcasts'),
  sendBroadcast: (text: string) => fetchJSON<{ ok: boolean; sent: number; error?: string }>('/admin/broadcast', {
    method: 'POST',
    body: JSON.stringify({ text }),
  }),
  adminEnableUser: (userId: number) => fetchJSON<{ ok: boolean }>(`/admin/users/${userId}/enable`, { method: 'POST' }),
  adminDisableUser: (userId: number) => fetchJSON<{ ok: boolean }>(`/admin/users/${userId}/disable`, { method: 'POST' }),
}

/** WebSocket live-uxlash. Backend manzil sifatida ws://host/api/ws */
export function liveStatus(onUpdate: (s: Status) => void, onClose?: () => void): () => void {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  let ws: WebSocket | null = null
  let closed = false

  const connect = () => {
    if (closed) return
    ws = new WebSocket(`${proto}://${location.host}/api/ws`)
    ws.onmessage = (e) => {
      try {
        onUpdate(JSON.parse(e.data))
      } catch { /* ignore */ }
    }
    ws.onclose = () => {
      if (!closed) {
        onClose?.()
        setTimeout(connect, 3000)
      }
    }
    ws.onerror = () => ws?.close()
  }
  connect()
  return () => {
    closed = true
    ws?.close()
  }
}

// format helpers
export const fmt = (n: number | null | undefined, dp = 2): string =>
  n === null || n === undefined ? '—' : n.toLocaleString('en-US', { maximumFractionDigits: dp, minimumFractionDigits: dp })

export const fmtMoney = (n: number | null | undefined, c = 'USD'): string =>
  `${(n ?? 0) < 0 ? '' : '+'}${fmt(n, 2)} ${c}`

export const fmtPct = (n: number | null | undefined): string =>
  `${(n ?? 0) < 0 ? '' : '+'}${fmt(n, 2)}%`