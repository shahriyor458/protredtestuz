import { useEffect, useState } from 'react'
import { api, fmt, fmtMoney } from '../api'

export default function TraderTrades() {
  const [trades, setTrades] = useState<any[]>([])
  const [filter, setFilter] = useState<'all' | 'open' | 'closed'>('all')
  const [loading, setLoading] = useState(true)
  const [closing, setClosing] = useState<number | null>(null)
  const [msg, setMsg] = useState('')

  const load = async () => {
    try {
      const r = await api.myTrades(200)
      setTrades(r.trades || [])
    } catch { /* */ }
    setLoading(false)
  }

  useEffect(() => {
    load()
    const iv = setInterval(load, 4000)
    return () => clearInterval(iv)
  }, [])

  const closeTrade = async (ticket: number) => {
    setClosing(ticket); setMsg('')
    try {
      const r = await api.closeMyTrade(ticket)
      if (!r.ok) setMsg('❌ ' + (r.error || 'Yopishda xato'))
      else setMsg('✅ Bitim yopildi')
    } catch (e: any) {
      setMsg('❌ ' + String(e))
    } finally {
      setClosing(null)
      load()
    }
  }

  const filtered = trades.filter(t => {
    if (filter === 'open') return t.status === 'open'
    if (filter === 'closed') return t.status === 'closed'
    return true
  })

  if (loading) return <div style={{ padding: 24 }}>Yuklanmoqda...</div>

  return (
    <div>
      <h2 style={{ marginBottom: 16 }}>📈 Platforma bitimlari (real-vaqt)</h2>
      {msg && <div style={{ padding: '8px 12px', borderRadius: 6, marginBottom: 12, fontSize: 13,
        background: msg.startsWith('✅') ? 'rgba(0,200,100,0.1)' : 'rgba(255,60,60,0.1)',
        border: `1px solid ${msg.startsWith('✅') ? 'rgba(0,200,100,0.3)' : 'rgba(255,60,60,0.3)'}` }}>{msg}</div>}
      <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
        {(['all', 'open', 'closed'] as const).map(f => (
          <button key={f} className={`btn ${filter === f ? 'btn-ok' : ''}`}
            style={{ fontSize: 12, padding: '4px 12px' }}
            onClick={() => setFilter(f)}>
            {f === 'all' ? 'Barchasi' : f === 'open' ? 'Ochiq' : 'Yopilgan'}
            {f === 'open' ? ` (${trades.filter(t => t.status === 'open').length})` : ''}
          </button>
        ))}
        <span className="muted" style={{ marginLeft: 'auto', fontSize: 12, alignSelf: 'center' }}>
          Yangilanmoqda: har 4 soniyada
        </span>
      </div>

      {filtered.length === 0 ? (
        <div className="card" style={{ padding: 24, textAlign: 'center', color: 'var(--muted)' }}>
          Hozircha bitimlar yo'q
        </div>
      ) : (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ borderBottom: '2px solid var(--line)' }}>
                <th style={{ textAlign: 'left', padding: '8px' }}>Simvol</th>
                <th style={{ textAlign: 'left', padding: '8px' }}>Yo'nalish</th>
                <th style={{ textAlign: 'right', padding: '8px' }}>Hajm</th>
                <th style={{ textAlign: 'right', padding: '8px' }}>Kirish</th>
                <th style={{ textAlign: 'right', padding: '8px' }}>SL</th>
                <th style={{ textAlign: 'right', padding: '8px' }}>TP</th>
                <th style={{ textAlign: 'right', padding: '8px' }}>P&L</th>
                <th style={{ textAlign: 'left', padding: '8px' }}>Holat</th>
                <th style={{ textAlign: 'left', padding: '8px' }}>Vaqt</th>
                <th style={{ textAlign: 'center', padding: '8px' }}></th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(t => (
                <tr key={t.ticket} style={{ borderBottom: '1px solid var(--line)' }}>
                  <td style={{ padding: '8px', fontWeight: 600 }}>{t.symbol}</td>
                  <td style={{ padding: '8px', color: t.direction === 'BUY' ? 'var(--green)' : 'var(--red)', fontWeight: 600 }}>
                    {t.direction === 'BUY' ? '🟢 BUY' : '🔴 SELL'}
                  </td>
                  <td style={{ padding: '8px', textAlign: 'right' }}>{fmt(t.volume, 2)}</td>
                  <td style={{ padding: '8px', textAlign: 'right' }}>{fmt(t.entry)}</td>
                  <td style={{ padding: '8px', textAlign: 'right' }}>{t.sl ? fmt(t.sl) : '—'}</td>
                  <td style={{ padding: '8px', textAlign: 'right' }}>{t.tp ? fmt(t.tp) : '—'}</td>
                  <td style={{ padding: '8px', textAlign: 'right', fontWeight: 600, color: (t.pnl || 0) >= 0 ? 'var(--green)' : 'var(--red)' }}>
                    {t.pnl != null ? fmtMoney(t.pnl) : '—'}
                  </td>
                  <td style={{ padding: '8px' }}>
                    {t.status === 'open' ? (
                      <span style={{ color: 'var(--accent)', fontSize: 12 }}>⏳ Ochiq</span>
                    ) : (
                      <span style={{ color: 'var(--muted)', fontSize: 12 }}>✓ {t.close_reason || 'yopildi'}</span>
                    )}
                  </td>
                  <td style={{ padding: '8px', fontSize: 11, color: 'var(--muted)' }}>
                    {t.opened_at ? new Date(t.opened_at).toLocaleString('uz-UZ') : '—'}
                  </td>
                  <td style={{ padding: '8px', textAlign: 'center' }}>
                    {t.status === 'open' && (
                      <button className="btn" style={{ fontSize: 11, padding: '3px 10px', color: 'var(--red)' }}
                        onClick={() => closeTrade(t.ticket)} disabled={closing === t.ticket}>
                        {closing === t.ticket ? '...' : '✋ Yopish'}
                      </button>
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