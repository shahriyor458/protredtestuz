import { useEffect, useState } from 'react'
import { api, AdminStats, AdminUser, fmt, fmtMoney } from '../api'

type Source = '' | 'web' | 'telegram'

export default function Members() {
  const [users, setUsers] = useState<AdminUser[]>([])
  const [stats, setStats] = useState<AdminStats | null>(null)
  const [source, setSource] = useState<Source>('')
  const [q, setQ] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    api.adminStats().then(setStats).catch(() => {})
  }, [])

  useEffect(() => {
    setLoading(true)
    api.adminUsers(source, q)
      .then((r) => setUsers(r.users))
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false))
  }, [source, q])

  const u = stats?.users

  const chips: { key: Source; label: string; value: number }[] = [
    { key: '', label: 'Hammasi', value: u?.total ?? 0 },
    { key: 'web', label: 'Web', value: u?.web ?? 0 },
    { key: 'telegram', label: 'Telegram bot', value: u?.telegram ?? 0 },
  ]

  return (
    <div>
      <div className="page-title">
        Aʼzolar
        <span className="muted" style={{ fontSize: 13 }}>
          Roʼyxatdan oʼtgan: <b style={{ color: 'var(--txt)' }}>{u?.total ?? 0}</b> · Bugun: {u?.new_today ?? 0} · Faol bugun: <b style={{ color: 'var(--green)' }}>{u?.active_today ?? 0}</b>
        </span>
      </div>

      {/* filtr */}
      <div className="flex section">
        {chips.map((c) => (
          <button
            key={c.key}
            className={`btn ${source === c.key ? 'btn-ok' : ''}`}
            onClick={() => setSource(c.key)}
          >
            {c.label} <b>({c.value})</b>
          </button>
        ))}
        <span className="spacer" />
        <input
          style={{ maxWidth: 260 }}
          placeholder="Qidirish: login, ism, telegram..."
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
      </div>

      {error && <div className="empty">Xatolik: {error}</div>}
      {loading && <div className="empty">Yuklanmoqda...</div>}
      {!loading && !error && users.length === 0 && (
        <div className="empty">Aʼzolar roʼyxati boʼsh.</div>
      )}

      {!loading && !error && users.length > 0 && (
        <div className="card">
          <table className="table">
            <thead>
              <tr>
                <th>#</th>
                <th>Aʼzo</th>
                <th>Manba</th>
                <th>Broker</th>
                <th>AI Robot</th>
                <th>Roʼyxatdan oʼtgan</th>
                <th>Savdolar</th>
                <th>Hajm (lot)</th>
                <th style={{ textAlign: 'right' }}>Realized P&amp;L</th>
                <th>Boshqaruv</th>
              </tr>
            </thead>
            <tbody>
              {users.map((x) => (
                <tr key={x.id}>
                  <td className="mono muted">{x.id}</td>
                  <td>
                    <b>{x.name || x.username || '—'}</b>
                    {x.username && <div className="muted" style={{ fontSize: 12 }}>@{x.username}</div>}
                  </td>
                  <td>
                    {x.source === 'web' ? (
                      <span className="tag tag-closed">Web</span>
                    ) : (
                      <span className="tag" style={{ background: 'var(--blue)', color: '#fff' }}>Telegram</span>
                    )}
                  </td>
                  <td>
                    {x.broker_connected ? (
                      <span style={{ color: 'var(--green)', fontSize: 12 }}>● Ulangan</span>
                    ) : (
                      <span style={{ color: 'var(--muted)', fontSize: 12 }}>● Ulanmagan</span>
                    )}
                    {x.risk_level !== 'moderate' && (
                      <div className="muted" style={{ fontSize: 11 }}>risk: {x.risk_level}</div>
                    )}
                  </td>
                  <td>
                    {x.trading_enabled ? (
                      <span className="tag" style={{ background: 'var(--green)', color: '#fff' }}>🟢 Faol</span>
                    ) : (
                      <span className="tag tag-closed">⚪ Oʻchiq</span>
                    )}
                    {x.paper_trading && <div className="muted" style={{ fontSize: 11 }}>🧪 paper</div>}
                  </td>
                  <td className="mono muted" style={{ fontSize: 12 }}>{x.created_at ? x.created_at.slice(0, 16).replace('T', ' ') : '—'}</td>
                  <td>{x.trade_count} ta</td>
                  <td className="mono">{fmt(x.trade_volume, 2)}</td>
                  <td className="mono" style={{ textAlign: 'right', color: x.realized_pnl >= 0 ? 'var(--green)' : 'var(--red)' }}>
                    {fmtMoney(x.realized_pnl)}
                  </td>
                  <td>
                    {x.username === 'shaxriyor' ? (
                      <span className="muted" style={{ fontSize: 11 }}>Admin</span>
                    ) : x.broker_connected ? (
                      x.trading_enabled ? (
                        <button className="btn" style={{ fontSize: 11, padding: '3px 10px' }}
                          onClick={() => api.adminDisableUser(x.id).then(() => api.adminUsers(source, q).then(r => setUsers(r.users)))}>
                          🛑 Oʻchirish
                        </button>
                      ) : (
                        <button className="btn btn-ok" style={{ fontSize: 11, padding: '3px 10px' }}
                          onClick={() => api.adminEnableUser(x.id).then(() => api.adminUsers(source, q).then(r => setUsers(r.users)))}>
                          ▶️ Yoqish
                        </button>
                      )
                    ) : (
                      <span className="muted" style={{ fontSize: 11 }}>Broker kutilmoqda</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}