import type { Status } from '../api'
import { fmt, fmtMoney, fmtPct } from '../api'

export default function Dashboard({ status }: { status: Status | null }) {
  if (!status) return <div className="empty">Yuklanmoqda...</div>

  const a = status.account
  const r = status.risk
  const u = status.unrealized
  const re = status.realized
  const cur = a?.currency || re.currency || 'USD'

  // balance breakdown bar (foizlarda, xavfsiz ishlash uchun)
  const bal = a?.balance || 0
  const eq = a?.equity || 0
  const marginShare = bal ? Math.min(100, (a?.margin || 0) / bal * 100) : 0
  const freeShare = bal ? Math.max(0, (a?.free_margin || 0) / bal * 100) : 0

  return (
    <div>
      <div className="page-title">
        Risk va Balans Boshqaruvi
        <span className={`conn-dot ${status.connected ? 'conn-on' : 'conn-off'}`} />
        <span className="muted" style={{ fontSize: 13 }}>{a?.broker} · {a?.server}</span>
      </div>

      {/* 1) Hisob balansi */}
      <div className="grid grid-3 section">
        <div className="card">
          <h3>Umumiy Balans</h3>
          <div style={{ fontSize: 26, fontWeight: 700, fontFamily: 'var(--mono)' }}>
            {fmt(bal, 2)} <span className="muted" style={{ fontSize: 15 }}>{cur}</span>
          </div>
          <div className="muted" style={{ marginTop: 6 }}>Equity: <b style={{ color: 'var(--txt)' }}>{fmt(eq, 2)}</b></div>
        </div>
        <div className="card">
          <h3>Ishlatilayotgan Marja</h3>
          <div style={{ fontSize: 26, fontWeight: 700, fontFamily: 'var(--mono)' }}>
            {fmt(a?.margin, 2)} <span className="muted" style={{ fontSize: 15 }}>{cur}</span>
          </div>
          <div className="muted" style={{ marginTop: 6 }}>
            Margin level: <b style={{ color: 'var(--amber)' }}>{fmt(a?.margin_level, 0)}%</b>
          </div>
        </div>
        <div className="card">
          <h3>Erkin Mablag'</h3>
          <div style={{ fontSize: 26, fontWeight: 700, fontFamily: 'var(--mono)' }}>
            {fmt(a?.free_margin, 2)} <span className="muted" style={{ fontSize: 15 }}>{cur}</span>
          </div>
          <div className="muted" style={{ marginTop: 6 }}>Kredit: <b style={{ color: 'var(--txt)' }}>{fmt(a?.leverage, 0)}:1</b></div>
        </div>
      </div>

      <div className="card section">
        <h3>Balans taqsimoti</h3>
        <div style={{ height: 14, background: 'var(--panel2)', borderRadius: 8, overflow: 'hidden', display: 'flex' }}>
          <div style={{ width: `${marginShare}%`, background: 'var(--blue)' }} title="Marja" />
          <div style={{ width: `${freeShare}%`, background: 'var(--green)' }} title="Free margin" />
          <div style={{ flex: 1, background: 'var(--red-bg)' }} title="Qolgan qismi (equity farqi)" />
        </div>
        <div className="flex" style={{ marginTop: 10, fontSize: 12, color: 'var(--muted)' }}>
          <span><span style={{ color: 'var(--blue)' }}>■</span> Marja {fmt(a?.margin, 2)}</span>
          <span><span style={{ color: 'var(--green)' }}>■</span> Free margin {fmt(a?.free_margin, 2)}</span>
          <span className="spacer" />
          <span>Ochiq: <b style={{ color: 'var(--txt)' }}>{u.open_count}</b></span>
        </div>
      </div>

      {/* 2) P&L paneli */}
      <div className="section">
        <div className="section-head">
          <h2>P&amp;L Panel</h2>
        </div>
        <div className="grid grid-3" style={{ marginBottom: 14 }}>
          <div className="card">
            <h3>Unrealized P&amp;L (Real-vaqt)</h3>
            <div className={`value`} style={{ fontSize: 26, fontWeight: 700, fontFamily: 'var(--mono)', color: u.unrealized_pnl >= 0 ? 'var(--green)' : 'var(--red)' }}>
              {fmtMoney(u.unrealized_pnl, cur)}
            </div>
            <div className={`sub`} style={{ color: u.unrealized_pnl >= 0 ? 'var(--green)' : 'var(--red)', fontFamily: 'var(--mono)' }}>
              {fmtPct(u.unrealized_pnl_pct)}
            </div>
          </div>
          <div className="card">
            <h3>Bugun (Realized)</h3>
            <div style={{ fontSize: 26, fontWeight: 700, fontFamily: 'var(--mono)', color: re.today >= 0 ? 'var(--green)' : 'var(--red)' }}>
              {fmtMoney(re.today, cur)}
            </div>
            <div className="sub muted" style={{ fontFamily: 'var(--mono)', color: re.today >= 0 ? 'var(--green)' : 'var(--red)' }}>
              {fmtPct(re.today_pct)}
            </div>
          </div>
          <div className="card">
            <h3>Kunlik maqsad</h3>
            <div className="flex" style={{ marginTop: 6 }}>
              <div className="metric" style={{ flex: 1 }}>
                <div className="label">P&amp;L kun</div>
                <div className="value" style={{ fontSize: 16, color: r.daily_profit_pct >= 0 ? 'var(--green)' : 'var(--red)' }}>
                  {fmtPct(r.daily_profit_pct)}
                </div>
              </div>
              <div className="metric" style={{ flex: 1 }}>
                <div className="label">Drawdown</div>
                <div className="value" style={{ fontSize: 16, color: r.current_drawdown_pct > r.max_daily_drawdown * 0.8 ? 'var(--red)' : 'var(--amber)' }}>
                  {fmt(r.current_drawdown_pct)}%
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="grid grid-4">
          {([
            ['7 kun', re.week, re.week_pct],
            ['30 kun', re.month, re.month_pct],
            ['Umumiy', re.total, re.total_pct],
          ] as const).map(([label, val, pct]) => (
            <div className="metric" key={label}>
              <div className="label">{label}</div>
              <div className="value" style={{ fontSize: 16, color: val >= 0 ? 'var(--green)' : 'var(--red)' }}>{fmtMoney(val, cur)}</div>
              <div className={`sub ${pct >= 0 ? 'num-up' : 'num-down'}`} style={{ fontFamily: 'var(--mono)' }}>{fmtPct(pct)}</div>
            </div>
          ))}
        </div>
      </div>

      {/* 3) Risk holati */}
      <div className="section">
        <div className="section-head">
          <h2>Xavf Darajasi</h2>
        </div>
        <div className="grid grid-3">
          <div className="card">
            <h3>Joriy daraja</h3>
            <div className={`risk-pill risk-${r.risk_level}`}>{r.risk_level.toUpperCase()} ({r.risk_band[0]}–{r.risk_band[1]}%)</div>
            <div className="muted" style={{ marginTop: 10 }}>
              Bir bitimga xavf: <b style={{ color: 'var(--gold)' }}>{fmt(r.risk_percent_per_trade, 1)}%</b>
            </div>
          </div>
          <div className="card">
            <h3>Limitlar</h3>
            <div className="muted" style={{ lineHeight: 1.9 }}>
              Maks kunlik drawdown: <b>{fmt(r.max_daily_drawdown, 1)}%</b><br />
              Kunlik savdo limiti: {r.max_daily_trades} ta<br />
              Maks ochiq pozitsiya: {r.max_open_positions} ta
            </div>
          </div>
          <div className="card">
            <h3>Signal filtri</h3>
            <div className="muted" style={{ lineHeight: 1.9 }}>
              Min confidence: <b>{fmt(r.min_confidence, 0)}%</b><br />
              Rejim: {r.paper_trading ? '🧪 PAPER (demo)' : '🔴 REAL'}
            </div>
          </div>
        </div>
      </div>

      {/* 4) Live signal xulosasi (Metal Index) */}
      <div className="section">
        <div className="section-head">
          <h2>Metal Index — AI Signal Xulosasi</h2>
        </div>
        <div className="grid grid-2">
          {Object.entries(status.signals).map(([symbol, txt]) => (
            <div className="card" key={symbol}>
              <div style={{ fontSize: 15, fontWeight: 700, marginBottom: 6 }}>{symbol}</div>
              <div className="mono" style={{ color: 'var(--gold)', fontSize: 13 }}>{txt}</div>
            </div>
          ))}
          {Object.keys(status.signals).length === 0 && (
            <div className="empty" style={{ gridColumn: '1 / -1', padding: 20 }}>
              Hali signal yo'q — AI bozorni tahlil qilmoqda...
            </div>
          )}
        </div>
      </div>
    </div>
  )
}