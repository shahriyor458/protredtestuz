import { useEffect, useState } from 'react'
import { api, fmt, fmtMoney, fmtPct } from '../api'

interface PnlData {
  realized: number
  unrealized: number
  total_trades: number
  wins: number
  losses: number
  winrate: number
}

function PnlChart({ series }: { series: { date: string; pnl: number; trades: number }[] }) {
  const max = Math.max(1, ...series.map(s => Math.abs(s.pnl)))
  return (
    <div className="barchart">
      {series.map(v => {
        const h = v.pnl ? Math.max(6, Math.round((Math.abs(v.pnl) / max) * 100)) : 2
        return (
          <div className="bar-col" key={v.date} title={`${v.date}: ${fmtMoney(v.pnl)} (${v.trades} ta)`}>
            <div className="bar" style={{ height: `${h}%`, background: v.pnl >= 0 ? 'var(--green)' : 'var(--red)' }} />
            <div className="bar-label">{v.date.slice(8)}</div>
          </div>
        )
      })}
    </div>
  )
}

export default function TraderDashboard() {
  const [pnl, setPnl] = useState<PnlData | null>(null)
  const [trades, setTrades] = useState<any[]>([])
  const [history, setHistory] = useState<{ date: string; pnl: number; trades: number }[]>([])
  const [robotStatus, setRobotStatus] = useState<any>(null)
  const [news, setNews] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [closing, setClosing] = useState<number | null>(null)

  const load = async () => {
    try {
      const [p, t, h, b, n] = await Promise.all([
        api.myPnl().catch(() => null),
        api.myTrades(50).catch(() => ({ trades: [] })),
        api.myPnlHistory(14).catch(() => ({ series: [] as any[] })),
        api.getBroker().catch(() => null),
        api.newsEvents().catch(() => ({ events: [] })),
      ])
      setPnl(p)
      setTrades(t.trades || [])
      setHistory(h.series || [])
      setRobotStatus(b)
      setNews(n.events || [])
    } catch (e: any) {
      setError(String(e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load(); const iv = setInterval(load, 4000); return () => clearInterval(iv) }, [])

  const closeTrade = async (ticket: number) => {
    setClosing(ticket)
    try {
      const r = await api.closeMyTrade(ticket)
      if (!r.ok) setError(r.error || 'Yopishda xato')
    } catch (e: any) {
      setError(String(e))
    } finally {
      setClosing(null)
      load()
    }
  }

  if (loading) return <div style={{ padding: 24 }}>Yuklanmoqda...</div>

  const openTrades = trades.filter(t => t.status === 'open')
  const closedTrades = trades.filter(t => t.status === 'closed')

  return (
    <div>
      <h2 style={{ marginBottom: 16 }}>📊 Savdo paneli</h2>
      {error && <div style={{ color: 'var(--red)', marginBottom: 12 }}>⚠️ {error}</div>}

      {/* Robot holati */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 12, marginBottom: 20 }}>
        <div className="card" style={{ padding: 16 }}>
          <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 4 }}>AI Robot</div>
          <div style={{ fontSize: 18, fontWeight: 600 }}>
            {robotStatus?.connected ? (
              <span style={{ color: 'var(--green)' }}>● 24/7 faol</span>
            ) : (
              <span style={{ color: 'var(--amber)' }}>● MT5 ochilishini kutmoqda</span>
            )}
          </div>
          <div style={{ fontSize: 12, color: 'var(--muted)' }}>
            Yagona server akkaunti #{robotStatus?.login || '—'} · {robotStatus?.server || ''}
            {robotStatus?.paper_trading ? ' · 🧪 Paper' : ' · 💰 Real'}
          </div>
        </div>
        <div className="card" style={{ padding: 16 }}>
          <div style={{ fontSize: 11, color: 'var(--muted)' }}>Realizatsiya qilingan foyda</div>
          <div style={{ fontSize: 22, fontWeight: 700, color: (pnl?.realized || 0) >= 0 ? 'var(--green)' : 'var(--red)' }}>
            {fmtMoney(pnl?.realized || 0)}
          </div>
          <div style={{ fontSize: 11, color: 'var(--muted)' }}>Ochiq P&L: <b style={{ color: (pnl?.unrealized || 0) >= 0 ? 'var(--green)' : 'var(--red)' }}>{fmtMoney(pnl?.unrealized || 0)}</b></div>
        </div>
        <div className="card" style={{ padding: 16 }}>
          <div style={{ fontSize: 11, color: 'var(--muted)' }}>Bitimlar</div>
          <div style={{ fontSize: 22, fontWeight: 700 }}>{pnl?.total_trades || 0}</div>
          <div style={{ fontSize: 11, color: 'var(--muted)' }}>Ochiq: {openTrades.length}</div>
        </div>
        <div className="card" style={{ padding: 16 }}>
          <div style={{ fontSize: 11, color: 'var(--muted)' }}>Yutuq darajasi</div>
          <div style={{ fontSize: 22, fontWeight: 700, color: (pnl?.winrate || 0) >= 50 ? 'var(--green)' : 'var(--red)' }}>
            {fmtPct(pnl?.winrate)}
          </div>
          <div style={{ fontSize: 11, color: 'var(--muted)' }}>{pnl?.wins}W / {pnl?.losses}L</div>
        </div>
      </div>

      {/* Yangiliklar */}
      {news.length > 0 && (
        <div className="card" style={{ padding: 16, marginBottom: 20 }}>
          <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 8 }}>Kelayotgan muhim yangiliklar</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {news.slice(0, 5).map((e, i) => (
              <div key={i} style={{ fontSize: 12, display: 'flex', gap: 10, alignItems: 'center' }}>
                <span style={{ color: e.impact === 'High' ? 'var(--red)' : 'var(--accent)', fontWeight: 600 }}>
                  {e.impact === 'High' ? '🔴' : '🟡'} {e.impact}</span>
                <span style={{ minWidth: 40 }}>{e.time_utc}</span>
                <span>{e.title}</span>
                <span style={{ color: 'var(--muted)', marginLeft: 'auto' }}>{e.currency}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Ochiq bitimlar (real-vaqt, yopish tugmasi bilan) */}
      <div style={{ marginBottom: 20 }}>
        <h3 style={{ marginBottom: 8 }}>📭 Ochiq bitimlar ({openTrades.length})</h3>
        {openTrades.length === 0 ? (
          <div className="card" style={{ padding: 20, textAlign: 'center', color: 'var(--muted)', fontSize: 13 }}>
            Hozircha ochiq bitim yo'q — AI bozorni tahlil qilmoqda...
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--line)' }}>
                  <th style={{ textAlign: 'left', padding: '6px 8px' }}>Simvol</th>
                  <th style={{ textAlign: 'left', padding: '6px 8px' }}>Yo'nalish</th>
                  <th style={{ textAlign: 'right', padding: '6px 8px' }}>Hajm</th>
                  <th style={{ textAlign: 'right', padding: '6px 8px' }}>Kirish</th>
                  <th style={{ textAlign: 'right', padding: '6px 8px' }}>Joriy</th>
                  <th style={{ textAlign: 'right', padding: '6px 8px' }}>P&L</th>
                  <th style={{ textAlign: 'center', padding: '6px 8px' }}></th>
                </tr>
              </thead>
              <tbody>
                {openTrades.map(t => (
                  <tr key={t.ticket} style={{ borderBottom: '1px solid var(--line)' }}>
                    <td style={{ padding: '6px 8px', fontWeight: 600 }}>{t.symbol}</td>
                    <td style={{ padding: '6px 8px', color: t.direction === 'BUY' ? 'var(--green)' : 'var(--red)', fontWeight: 600 }}>
                      {t.direction === 'BUY' ? '🟢 BUY' : '🔴 SELL'}
                    </td>
                    <td style={{ padding: '6px 8px', textAlign: 'right' }}>{fmt(t.volume, 2)}</td>
                    <td style={{ padding: '6px 8px', textAlign: 'right' }}>{fmt(t.entry)}</td>
                    <td style={{ padding: '6px 8px', textAlign: 'right' }}>{t.current ? fmt(t.current) : '—'}</td>
                    <td style={{ padding: '6px 8px', textAlign: 'right', fontWeight: 600, color: (t.pnl || 0) >= 0 ? 'var(--green)' : 'var(--red)' }}>
                      {fmtMoney(t.pnl)}
                    </td>
                    <td style={{ padding: '6px 8px', textAlign: 'center' }}>
                      <button className="btn" style={{ fontSize: 12, padding: '3px 10px' }}
                        onClick={() => closeTrade(t.ticket)} disabled={closing === t.ticket}>
                        {closing === t.ticket ? 'Yopilmoqda...' : '✋ Yopish'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* P&L diagramma */}
      <div className="card" style={{ padding: 16, marginBottom: 20 }}>
        <div className="flex" style={{ marginBottom: 12 }}>
          <h3 style={{ margin: 0 }}>📈 Foyda-zarar (kunlik)</h3>
          <span className="muted" style={{ fontSize: 12 }}>Oxirgi 14 kun</span>
        </div>
        <div style={{ height: 120 }}>
          <PnlChart series={history} />
        </div>
      </div>

      {/* Oxirgi yopilgan bitimlar */}
      {closedTrades.length > 0 && (
        <div>
          <h3 style={{ marginBottom: 8 }}>📜 Oxirgi bitimlar</h3>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--line)' }}>
                  <th style={{ textAlign: 'left', padding: '6px 8px' }}>Simvol</th>
                  <th style={{ textAlign: 'left', padding: '6px 8px' }}>Yo'nalish</th>
                  <th style={{ textAlign: 'right', padding: '6px 8px' }}>P&L</th>
                  <th style={{ textAlign: 'left', padding: '6px 8px' }}>Sabab</th>
                </tr>
              </thead>
              <tbody>
                {closedTrades.slice(0, 10).map(t => (
                  <tr key={t.ticket} style={{ borderBottom: '1px solid var(--line)' }}>
                    <td style={{ padding: '6px 8px' }}>{t.symbol}</td>
                    <td style={{ padding: '6px 8px', color: t.direction === 'BUY' ? 'var(--green)' : 'var(--red)' }}>
                      {t.direction}
                    </td>
                    <td style={{ padding: '6px 8px', textAlign: 'right', color: (t.pnl || 0) >= 0 ? 'var(--green)' : 'var(--red)' }}>
                      {fmtMoney(t.pnl)}
                    </td>
                    <td style={{ padding: '6px 8px' }}>{t.close_reason || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}