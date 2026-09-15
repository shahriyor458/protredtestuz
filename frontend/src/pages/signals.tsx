import { useCallback, useEffect, useState } from 'react'
import { api, fmt, Signal } from '../api'

export default function Signals() {
  const [signals, setSignals] = useState<Signal[]>([])
  const [loading, setLoading] = useState(true)

  const load = useCallback(() => {
    api.signals(150).then((r) => setSignals(r.signals)).catch(() => {}).finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    load()
    const t = setInterval(load, 15000)
    return () => clearInterval(t)
  }, [load])

  return (
    <div>
      <div className="page-title">Metal Index — AI Signal Loglari</div>
      <div className="muted" style={{ marginBottom: 16, fontSize: 13 }}>
        Indikator konfluensiyasi, rejim, confidence va savdo natijani o'z ichiga oladigan professional tahlil jurnali.
      </div>

      {loading && signals.length === 0 && <div className="empty">Yuklanmoqda...</div>}
      {!loading && signals.length === 0 && (
        <div className="empty">
          Signal hali chiqmagan. AI har {''}daqiqada bozorni skan qiladi — konfluensiya yetarli bo'lganida signal yoziladi.
        </div>
      )}

      {signals.map((s) => (
        <div className="card" key={s.id} style={{ marginBottom: 10 }}>
          <div className="flex" style={{ marginBottom: 8 }}>
            <b style={{ fontSize: 15 }}>{s.symbol}</b>
            <span className={`tag ${s.direction === 'BUY' ? 'tag-buy' : 'tag-sell'}`}>{s.direction}</span>
            {s.applied
              ? <span className="tag tag-open">✅ Bajarildi #{s.id}</span>
              : <span className="tag tag-closed">▫️ Faqat signal</span>}
            <span className="spacer" />
            <span className="muted mono" style={{ fontSize: 12 }}>
              {new Date(s.created_at).toLocaleString()} · {s.timeframe} · {s.regime}
            </span>
          </div>

          <div className="grid grid-4" style={{ marginBottom: 10 }}>
            <div className="metric">
              <div className="label">Kirish narxi</div>
              <div className="value" style={{ fontSize: 15 }}>{fmt(s.entry)}</div>
            </div>
            <div className="metric">
              <div className="label">Stop Loss</div>
              <div className="value num-down" style={{ fontSize: 15 }}>{fmt(s.stop_loss)}</div>
            </div>
            <div className="metric">
              <div className="label">Take Profit</div>
              <div className="value num-up" style={{ fontSize: 15 }}>{fmt(s.take_profit)}</div>
            </div>
            <div className="metric">
              <div className="label">Confidence</div>
              <div className="value gold" style={{ fontSize: 15 }}>{fmt(s.confidence, 0)}%</div>
            </div>
          </div>

          <div style={{ fontSize: 12.5 }}>
            {s.reasons.map((r, i) => (
              <div key={i} className="muted" style={{ marginBottom: 3 }}>• {r}</div>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}