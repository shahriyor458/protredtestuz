import { useEffect, useState } from 'react'
import { api, liveStatus, Status, setToken, getToken, setUserToken, getUserToken, setUserRole, getUserRole, clearAuth } from './api'
import Overview from './pages/Overview'
import Members from './pages/Members'
import BotPage from './pages/BotPage'
import Dashboard from './pages/Dashboard'
import Trades from './pages/Trades'
import Signals from './pages/Signals'
import Settings from './pages/Settings'
import Events from './pages/Events'
import TraderDashboard from './pages/TraderDashboard'
import TraderTrades from './pages/TraderTrades'
import TraderSettings from './pages/TraderSettings'

type AdminPage = 'overview' | 'members' | 'bot' | 'dashboard' | 'trades' | 'signals' | 'settings' | 'events'
type TraderPage = 'tdashboard' | 'ttrades' | 'tsettings'

const ADMIN_NAV: { key: AdminPage; label: string }[] = [
  { key: 'overview', label: '📊 Bosh Panel' },
  { key: 'members', label: '👥 Aʼzolar' },
  { key: 'bot', label: '🤖 Bot Sahifasi' },
  { key: 'dashboard', label: 'Risk va Balans' },
  { key: 'trades', label: 'Ochiq Bitimlar' },
  { key: 'signals', label: 'AI Signallar' },
  { key: 'settings', label: 'Sozlamalar' },
  { key: 'events', label: 'Jurnallar' },
]

const TRADER_NAV: { key: TraderPage; label: string }[] = [
  { key: 'tdashboard', label: '📊 Dashboard' },
  { key: 'ttrades', label: '📈 Bitimlarim' },
  { key: 'tsettings', label: '⚙️ Sozlamalar' },
]

export default function App() {
  const [adminPage, setAdminPage] = useState<AdminPage>('overview')
  const [traderPage, setTraderPage] = useState<TraderPage>('tdashboard')
  const [status, setStatus] = useState<Status | null>(null)
  const [role, setRole] = useState<string>(getUserRole())
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [loginErr, setLoginErr] = useState('')
  const [logging, setLogging] = useState(false)
  const [showLogin, setShowLogin] = useState(!getToken() && !getUserToken())
  const [showRegister, setShowRegister] = useState(false)
  const [regName, setRegName] = useState('')

  useEffect(() => {
    if (!showLogin) {
      const off = liveStatus(setStatus)
      api.status().then(setStatus).catch(() => {})
      return off
    }
  }, [showLogin])

  const doLogin = async () => {
    setLogging(true)
    setLoginErr('')
    try {
      const r = await api.login(username.trim(), password)
      if (!r.ok) throw new Error('Login xato')
      if (r.role === 'admin') {
        // admin token ham olish kerak
        const ar = await api.adminLogin(username.trim(), password)
        setToken(ar.token)
        setUserToken(r.user.token)
        setUserRole('admin')
        setRole('admin')
      } else {
        setUserToken(r.user.token)
        setUserRole('user')
        setRole('user')
      }
      setShowLogin(false)
    } catch (e) {
      setLoginErr(String(e))
    } finally {
      setLogging(false)
    }
  }

  const doRegister = async () => {
    setLogging(true)
    setLoginErr('')
    try {
      const r = await api.register(username.trim(), regName.trim() || username.trim(), password)
      if (!r.ok) throw new Error('Registration xato')
      setUserToken(r.user.token)
      setUserRole('user')
      setRole('user')
      setShowLogin(false)
    } catch (e) {
      setLoginErr(String(e))
    } finally {
      setLogging(false)
    }
  }

  const logout = () => {
    clearAuth()
    setRole('')
    setShowLogin(true)
  }

  // ─── LOGIN / REGISTER ─────────────────────
  if (showLogin) {
    return (
      <div style={{ display: 'grid', placeItems: 'center', minHeight: '100vh' }}>
        <div className="card" style={{ width: 400 }}>
          <h3 style={{ textAlign: 'center', marginBottom: 4 }}>
            {showRegister ? '📝 Ro\'yxatdan o\'tish' : '🔐 Kirish'}
          </h3>
          <p className="muted" style={{ textAlign: 'center', marginBottom: 16, fontSize: 13 }}>
            {showRegister
              ? 'Hisob yarating — AI Robot siz uchun savdo qiladi'
              : 'Admin yoki trader hisobiga kiring'}
          </p>
          {showRegister && (
            <div className="field">
              <label>To'liq ism</label>
              <input value={regName} onChange={e => setRegName(e.target.value)} placeholder="Ismingiz" />
            </div>
          )}
          <div className="field">
            <label>Login</label>
            <input value={username} onChange={e => setUsername(e.target.value)}
              placeholder="shaxriyor / sizning_login" onKeyDown={e => e.key === 'Enter' && (showRegister ? doRegister() : doLogin())} />
          </div>
          <div className="field">
            <label>Parol</label>
            <input type="password" value={password} onChange={e => setPassword(e.target.value)}
              placeholder="••••" onKeyDown={e => e.key === 'Enter' && (showRegister ? doRegister() : doLogin())} />
          </div>
          {loginErr && <div style={{ color: 'var(--red)', fontSize: 13, marginBottom: 10 }}>❌ {loginErr}</div>}
          <button className="btn btn-ok" style={{ width: '100%' }} onClick={showRegister ? doRegister : doLogin}
            disabled={logging || !username.trim() || !password}>
            {logging ? 'Kutilmoqda...' : showRegister ? 'Ro\'yxatdan o\'tish' : 'Kirish'}
          </button>
          <div style={{ textAlign: 'center', marginTop: 12 }}>
            <button style={{ background: 'none', border: 'none', color: 'var(--accent)', cursor: 'pointer', fontSize: 13 }}
              onClick={() => { setShowRegister(!showRegister); setLoginErr('') }}>
              {showRegister ? 'Hisobingiz bormi? Kirish' : 'Hisob yo\'qmi? Ro\'yxatdan o\'ting'}
            </button>
          </div>
        </div>
      </div>
    )
  }

  // ─── ADMIN PANEL ────────────────────────────
  if (role === 'admin') {
    return (
      <div className="layout">
        <aside className="sidebar">
          <div className="logo">PRO TRED<span>ADMIN PANEL</span></div>
          {ADMIN_NAV.map(n => (
            <div key={n.key} className={`nav-item ${adminPage === n.key ? 'active' : ''}`}
              onClick={() => setAdminPage(n.key)}>{n.label}</div>
          ))}
          <div style={{ marginTop: 16, padding: '10px 12px', borderTop: '1px dashed var(--line)', fontSize: 12, color: 'var(--muted)' }}>
            {status?.connected ? <span className="gold">● MT5 ulangan</span> : <span className="num-down">● MT5 ulanmagan</span>}
            <div style={{ marginTop: 6 }}>{status?.account?.broker || '—'}{status?.account?.login ? ` · #${status.account.login}` : ''}</div>
            {status?.risk.paper_trading && <div className="muted" style={{ marginTop: 4 }}>🧪 Paper rejim</div>}
          </div>
          <div style={{ marginTop: 'auto', padding: '10px 12px' }}>
            <button style={{ background: 'none', border: '1px solid var(--line)', color: 'var(--muted)', cursor: 'pointer', width: '100%', padding: 6, borderRadius: 4, fontSize: 12 }} onClick={logout}>Chiqish</button>
          </div>
        </aside>
        <main className="main">
          {adminPage === 'overview' && <Overview />}
          {adminPage === 'members' && <Members />}
          {adminPage === 'bot' && <BotPage />}
          {adminPage === 'dashboard' && <Dashboard status={status} />}
          {adminPage === 'trades' && <Trades status={status} />}
          {adminPage === 'signals' && <Signals />}
          {adminPage === 'settings' && <Settings status={status} />}
          {adminPage === 'events' && <Events />}
        </main>
      </div>
    )
  }

  // ─── TRADER PANEL ───────────────────────────
  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="logo">AI PRO TRADE<span>SAVDO PANELI</span></div>
        {TRADER_NAV.map(n => (
          <div key={n.key} className={`nav-item ${traderPage === n.key ? 'active' : ''}`}
            onClick={() => setTraderPage(n.key)}>{n.label}</div>
        ))}
        <div style={{ marginTop: 'auto', padding: '10px 12px' }}>
          <button style={{ background: 'none', border: '1px solid var(--line)', color: 'var(--muted)', cursor: 'pointer', width: '100%', padding: 6, borderRadius: 4, fontSize: 12 }} onClick={logout}>Chiqish</button>
        </div>
      </aside>
      <main className="main">
        {traderPage === 'tdashboard' && <TraderDashboard />}
        {traderPage === 'ttrades' && <TraderTrades />}
        {traderPage === 'tsettings' && <TraderSettings />}
      </main>
    </div>
  )
}
