import { useEffect, useState } from 'react'
import { api, AdminStats, DaySeries, fmt, fmtMoney } from '../api'

function BarChart({ series, color, label, height = 180 }: {
  series: DaySeries[]
  color: string
  label: (v: DaySeries) => number
  height?: number
}) {
  const max = Math.max(1, ...series.map(label))
  return (
    <div className="barchart" style={{ height }}>
      {series.map((v) => {
        const val = label(v)
        const h = val ? Math.max(6, Math.round((val / max) * 100)) : 2
        return (
          <div className="bar-col" key={v.date} title={`${v.date}: ${val}`}>
            <div className="bar" style={{ height: `${h}%`, background: val ? color : 'var(--line)' }} />
            <div className="bar-label">{v.date.slice(8)}</div>
          </div>
        )
      })}
    </div>
  )
}

function PnlBar({ series }: { series: { date: string; pnl: number; trades: number }[] }) {
  const max = Math.max(1, ...series.map(s => Math.abs(s.pnl)))
  return (
    <div className="barchart" style={{ height: 180 }}>
      {series.map((v) => {
        const val = Math.abs(v.pnl)
        const h = val ? Math.max(6, Math.round((val / max) * 100)) : 2
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

export default function Overview() {
  const [stats, setStats] = useState<AdminStats | null>(null)
  const [reg, setReg] = useState<DaySeries[]>([])
  const [dau, setDau] = useState<DaySeries[]>([])
  const [days, setDays] = useState(14)
  const [error, setError] = useState('')

  const load = () => {
    api.adminStats().then(setStats).catch((e) => setError(String(e)))
    api.adminRegistrations(days).then((r) => setReg(r.series)).catch(() => {})
    api.adminDau(days).then((r) => setDau(r.series)).catch(() => {})
  }

  useEffect(load, [days])

  if (error) return <div className="empty">Xatolik: {error}</div>
  if (!stats) return <div className="empty">Yuklanmoqda...</div>

  const u = stats.users
  const ins = stats.instruments
  const cur = stats.live.currency || 'USD'
  const pnl = stats.pnl
  const pnlHistory = stats.pnl_history || []
  const topActive = stats.top_active || []

  const cards: { label: string; value: string; sub?: React.ReactNode }[] = [
    { label: 'Jami aʼzolar', value: `${u.total}`, sub: <span><span className="tag tag-closed">Web {u.web}</span> <span className="tag" style={{ background: 'var(--blue)', color: '#fff' }}>Bot {u.telegram}</span></span> },
    { label: 'Savdo ochganlar', value: `${ins.users_with_trades}`, sub: `Jami bitimlar: ${ins.total_trades}` },
    { label: 'Umumiy hajm (lot)', value: fmt(ins.total_volume, 2) },
    { label: 'Bugungi faol (DAU)', value: `${u.active_today}`, sub: `Bugun yangi: ${u.new_today}` },
  ]

  return (
    <div>
      <div className="page-title">
        Bosh Panel — Platforma
        <span className={stats.live.connected ? 'conn-dot conn-on' : 'conn-dot conn-off'} />
        <span className="muted" style={{ fontSize: 13 }}>
          {stats.live.connected ? 'Robot ishlamoqda' : 'MT5 ulanmagan'} · Balans {fmt(stats.live.balance, 2)} {cur}
        </span>
      </div>

      {/* Asosiy ko'rsatkichlar */}
      <div className="grid grid-4 section">
        {cards.map((c) => (
          <div className="card" key={c.label}>
            <h3>{c.label}</h3>
            <div style={{ fontSize: 26, fontWeight: 700, fontFamily: 'var(--mono)' }}>{c.value}</div>
            <div className="muted" style={{ marginTop: 8, fontSize: 12 }}>{c.sub}</div>
          </div>
        ))}
      </div>

      {/* Instrumentlar bo'yicha savdo hajmi */}
      <div className="card section">
        <div className="flex" style={{ marginBottom: 12 }}>
          <h3 style={{ margin: 0 }}>Instrumentlarda qancha mablagʼ aylanmoqda</h3>
          <span className="muted" style={{ fontSize: 12 }}>
            Ochiq pozitsiyalar: {stats.live.open_positions} · Equity {fmt(stats.live.equity, 2)} {cur}
          </span>
        </div>
        {ins.by_symbol.length === 0 ? (
          <div className="empty" style={{ padding: 20 }}>Hali savdo bitimlari yoʼq.</div>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Instrument</th>
                <th>Bitimlar</th>
                <th>BUY/SELL</th>
                <th>Hajm (lot)</th>
                <th style={{ textAlign: 'right' }}>P&amp;L</th>
              </tr>
            </thead>
            <tbody>
              {ins.by_symbol.map((s) => (
                <tr key={s.symbol}>
                  <td><b className="mono">{s.symbol}</b></td>
                  <td>{s.count} ta</td>
                  <td><span className="tag tag-buy">{s.buys}</span> / <span className="tag tag-sell">{s.sells}</span></td>
                  <td className="mono">{fmt(s.volume, 2)}</td>
                  <td className="mono" style={{ textAlign: 'right', color: s.pnl >= 0 ? 'var(--green)' : 'var(--red)' }}>
                    {fmtMoney(s.pnl, cur)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Analitika */}
      <div className="section-head" style={{ marginTop: 8 }}>
        <h2>Analitika</h2>
        <select value={days} onChange={(e) => setDays(Number(e.target.value))} style={{ width: 90 }}>
          {[7, 14, 30].map((d) => <option key={d} value={d}>Soʼnggi {d} kun</option>)}
        </select>
      </div>
      <div className="grid grid-2 section">
        <div className="card">
          <h3>Roʼyxatdan oʼtish (Web / Telegram)</h3>
          <div style={{ height: 180 }}>
            <BarChart series={reg} color="var(--blue)" label={(v) => (v.web || 0) + (v.telegram || 0)} />
          </div>
          <div className="flex" style={{ marginTop: 8, fontSize: 12, color: 'var(--muted)' }}>
            <span><span style={{ color: 'var(--blue)' }}>■</span> Web</span>
            <span><span style={{ color: 'var(--green)' }}>■</span> Telegram</span>
          </div>
        </div>
        <div className="card">
          <h3>Kunlik faol foydalanuvchilar (DAU)</h3>
          <div style={{ height: 180 }}>
            <BarChart series={dau} color="var(--green)" label={(v) => v.active || 0} />
          </div>
          <div className="muted" style={{ marginTop: 8, fontSize: 12 }}>
            Oxirgi 24 soat: <b style={{ color: 'var(--txt)' }}>{u.active_today}</b> · Jami faol: <b style={{ color: 'var(--txt)' }}>{u.active}</b>
          </div>
        </div>
      </div>

      {/* Foyda-zarar analitikasi */}
      <div className="card section">
        <div className="flex" style={{ marginBottom: 12 }}>
          <h3 style={{ margin: 0 }}>📈 Foyda-zarar analitikasi</h3>
          <span className="muted" style={{ fontSize: 12 }}>
            Realizatsiya: <b style={{ color: pnl?.realized >= 0 ? 'var(--green)' : 'var(--red)' }}>{fmtMoney(pnl?.realized, cur)}</b>
            · Ochiq: {fmtMoney(pnl?.unrealized, cur)} · Yutuq darajasi: {fmt(pnl?.winrate, 1)}%
          </span>
        </div>
        <div className="grid grid-4" style={{ marginBottom: 16 }}>
          {([
            ['Bitimlar', pnl?.total_trades],
            ['Yutuqlar', pnl?.wins],
            ["Mag'lubiyatlar", pnl?.losses],
            ['Ochiq pozitsiya', pnl?.open_count],
          ] as const).map(([label, val]) => (
            <div className="metric" key={label}>
              <div className="label">{label}</div>
              <div className="value" style={{ fontSize: 20 }}>{val ?? 0}</div>
            </div>
          ))}
        </div>
        <div style={{ height: 180 }}>
          <PnlBar series={pnlHistory} />
        </div>
      </div>

      {/* Eng faol foydalanuvchilar */}
      <div className="card section">
        <div className="flex" style={{ marginBottom: 12 }}>
          <h3 style={{ margin: 0 }}>🔥 Eng faol foydalanuvchilar</h3>
          <span className="muted" style={{ fontSize: 12 }}>Loginlar soni boʼyicha top-10</span>
        </div>
        {topActive.length === 0 ? (
          <div className="empty" style={{ padding: 20 }}>Hali faollik yoʼq.</div>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>#</th>
                <th>Foydalanuvchi</th>
                <th>Manba</th>
                <th>Loginlar</th>
                <th>Tashriflar</th>
                <th>Oxirgi faollik</th>
              </tr>
            </thead>
            <tbody>
              {topActive.map((t, i) => (
                <tr key={t.id}>
                  <td><b>{i + 1}</b></td>
                  <td>
                    <b>{t.name || t.username || '—'}</b>
                    {t.username && <span className="muted" style={{ fontSize: 11 }}> (@{t.username})</span>}
                  </td>
                  <td><span className="tag" style={{ background: t.source === 'telegram' ? 'var(--blue)' : 'var(--panel2)' }}>{t.source}</span></td>
                  <td className="mono">{t.login_count}</td>
                  <td className="mono">{t.visits}</td>
                  <td style={{ fontSize: 12, color: 'var(--muted)' }}>{t.last_active_at ? new Date(t.last_active_at).toLocaleString('uz-UZ') : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}