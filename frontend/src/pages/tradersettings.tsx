import { useEffect, useState } from 'react'
import { api, fmt } from '../api'

export default function TraderSettings() {
  const [robotStatus, setRobotStatus] = useState<any>(null)
  const [risk, setRisk] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const load = async () => {
      try {
        const b = await api.getBroker().catch(() => null)
        setRobotStatus(b)
        const s = await api.status().catch(() => null)
        setRisk(s?.risk || null)
      } catch { /* */ }
      setLoading(false)
    }
    load()
    const iv = setInterval(load, 10000)
    return () => clearInterval(iv)
  }, [])

  if (loading) return <div style={{ padding: 24 }}>Yuklanmoqda...</div>

  return (
    <div>
      <h2 style={{ marginBottom: 20 }}>⚙️ AI Robot ma'lumotlari</h2>

      <div className="card" style={{ padding: 20, marginBottom: 16 }}>
        <h3 style={{ marginBottom: 12 }}>🤖 AI Robot (yagona server akkaunti)</h3>
        <div style={{ fontSize: 15, marginBottom: 8 }}>
          Holat: {robotStatus?.connected ? (
            <span style={{ color: 'var(--green)', fontWeight: 600 }}>● 24/7 faol — savdo qilmoqda</span>
          ) : (
            <span style={{ color: 'var(--amber)', fontWeight: 600 }}>● MT5 terminal ochilishini kutmoqda</span>
          )}
        </div>
        <div style={{ fontSize: 13, color: 'var(--muted)', lineHeight: 1.8 }}>
          <div>MT5 akkaunt: <b style={{ color: 'var(--txt)' }}>#{robotStatus?.login || '—'}</b> ({robotStatus?.server || '—'})</div>
          <div>Rejim: {robotStatus?.paper_trading ? '🧪 Paper (simulyatsiya)' : '💰 Real savdo'}</div>
        </div>
        <div style={{ marginTop: 14, padding: '12px 14px', borderRadius: 6,
          background: 'rgba(255,180,0,0.08)', border: '1px solid rgba(255,180,0,0.25)',
          fontSize: 13, color: 'var(--amber)' }}>
          Akkauntni qo'lda kiritish shart emas. AI Robot serverdagi yagona MT5 akkauntida
          24/7 avtomatik ishlaydi. Barcha bitimlar real-vaqtda panelda ko'rinadi va paneldan yopish mumkin.
        </div>
      </div>

      {risk && (
        <div className="card" style={{ padding: 20 }}>
          <h3 style={{ marginBottom: 12 }}>📊 Robot risk rejimi</h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 12 }}>
            <div>
              <div style={{ fontSize: 12, color: 'var(--muted)' }}>Risk darajasi</div>
              <div className="risk-pill" style={{ display: 'inline-block', marginTop: 6 }}>{String(risk.risk_level).toUpperCase()}</div>
            </div>
            <div>
              <div style={{ fontSize: 12, color: 'var(--muted)' }}>Kunlik savdo limiti</div>
              <div style={{ fontSize: 18, fontWeight: 700 }}>{risk.max_daily_trades} ta</div>
            </div>
            <div>
              <div style={{ fontSize: 12, color: 'var(--muted)' }}>Min confidence</div>
              <div style={{ fontSize: 18, fontWeight: 700 }}>{fmt(risk.min_confidence, 0)}%</div>
            </div>
            <div>
              <div style={{ fontSize: 12, color: 'var(--muted)' }}>Bugun ochilgan</div>
              <div style={{ fontSize: 18, fontWeight: 700 }}>{risk.trades_today} ta</div>
            </div>
            <div>
              <div style={{ fontSize: 12, color: 'var(--muted)' }}>Max ochiq pozitsiya</div>
              <div style={{ fontSize: 18, fontWeight: 700 }}>{risk.max_open_positions} ta</div>
            </div>
            <div>
              <div style={{ fontSize: 12, color: 'var(--muted)' }}>Bugungi daromad</div>
              <div style={{ fontSize: 18, fontWeight: 700, color: (risk.daily_profit_pct || 0) >= 0 ? 'var(--green)' : 'var(--red)' }}>
                {fmt(risk.daily_profit_pct || 0, 2)}%
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}