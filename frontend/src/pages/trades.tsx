import { useCallback, useEffect, useState } from 'react'
import { api, fmt, fmtMoney, Status, TradeRow } from '../api'

export default function Trades({ status }: { status: Status | null }) {
  const open = status?.unrealized.positions || []
  const [history, setHistory] = useState<TradeRow[]>([])
  const [toast, setToast] = useState<string | null>(null)
  const [busy, setBusy] = useState<number | null>(null)

  const loadHistory = useCallback(() => {
    api.trades(false).then((r) => setHistory(r.trades)).catch(() => {})
  }, [])

  useEffect(() => {
    loadHistory()
  }, [loadHistory])

  const closePos = async (ticket: number) => {
    setBusy(ticket)
    try {
      const res = await api.closePosition(ticket)
      setToast(res.ok ? `#${ticket} yopildi` : `Xato: ${res.error}`)
    } catch (e) {
      setToast(`Xato: ${(e as Error).message}`)
    } finally {
      setBusy(null)
      setTimeout(() => setToast(null), 3500)
    }
  }

  return (
    <div>
      <div className="page-title">Real-vaqt Ochiq Bitimlar</div>

      <div className="card section" style={{ padding: 0, overflow: 'hidden' }}>
        <table className="table">
          <thead>
            <tr>
              <th>Aktiv</th>
              <th>Tur</th>
              <th>Hajm</th>
              <th>Kirish</th>
              <th>Joriy</th>
              <th>TP</th>
              <th>SL</th>
              <th>Floating P&amp;L</th>
              <th style={{ textAlign: 'right' }}>Amal</th>
            </tr>
          </thead>
          <tbody>
            {open.length === 0 && (
              <tr><td colSpan={9} className="empty">Ochiq pozitsiya yo'q</td></tr>
            )}
            {open.map((p) => {
              const cur = status?.account?.currency || 'USD'
              const bal = status?.account?.balance || 0
              const pct = bal ? (p.profit / bal) * 100 : 0
              const pnlCls = p.profit >= 0 ? 'num-up' : 'num-down'
              return (
                <tr key={p.ticket}>
                  <td><b>{p.symbol}</b></td>
                  <td><span className={`tag ${p.direction === 'BUY' ? 'tag-buy' : 'tag-sell'}`}>{p.direction}</span></td>
                  <td className="mono">{p.volume}</td>
                  <td className="mono">{fmt(p.entry)}</td>
                  <td className="mono" style={{ color: p.current >= p.entry ? 'var(--green)' : 'var(--red)' }}>{fmt(p.current)}</td>
                  <td className="mono muted">{p.tp ? fmt(p.tp) : '—'}</td>
                  <td className="mono muted">{p.sl ? fmt(p.sl) : '—'}</td>
                  <td>
                    <span className={`mono ${pnlCls}`}>{fmtMoney(p.profit, cur)}</span>
                    <div className={`muted mono ${pnlCls}`} style={{ fontSize: 11 }}>{pct >= 0 ? '+' : ''}{fmt(pct, 2)}%</div>
                  </td>
                  <td style={{ textAlign: 'right' }}>
                    <button
                      className="btn btn-danger"
                      disabled={busy === p.ticket}
                      onClick={() => closePos(p.ticket)}
                    >
                      {busy === p.ticket ? 'Yopilmoqda...' : '✕ Close'}
                    </button>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      <div className="section">
        <div className="section-head">
          <h2>Bitimlar tarixi</h2>
          <button className="btn" onClick={loadHistory}>Yangilash</button>
        </div>
        <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
          <table className="table">
            <thead>
              <tr>
                <th>Ticket</th>
                <th>Simvol</th>
                <th>Tur</th>
                <th>Hajm</th>
                <th>Kirish</th>
                <th>Yopilgan</th>
                <th>P&amp;L</th>
                <th>Sabab</th>
                <th>Holat</th>
              </tr>
            </thead>
            <tbody>
              {history.slice(0, 40).map((t) => (
                <tr key={`${t.ticket}-${t.status}-${t.closed_at || t.opened_at}`}>
                  <td className="mono muted">#{t.ticket}</td>
                  <td><b>{t.symbol}</b></td>
                  <td><span className={`tag ${t.direction === 'BUY' ? 'tag-buy' : 'tag-sell'}`}>{t.direction}</span></td>
                  <td className="mono">{t.volume}</td>
                  <td className="mono">{fmt(t.entry)}</td>
                  <td className="mono muted">{t.closed_at ? new Date(t.closed_at).toLocaleString() : '—'}</td>
                  <td className={`mono ${(t.pnl || 0) >= 0 ? 'num-up' : 'num-down'}`}>{fmtMoney(t.pnl, status?.account?.currency || 'USD')}</td>
                  <td className="muted">{t.close_reason || '—'}</td>
                  <td>
                    <span className={`tag ${t.status === 'open' ? 'tag-open' : 'tag-closed'}`}>
                      {t.status === 'open' ? 'Ochiq' : 'Yopilgan'}
                    </span>
                  </td>
                </tr>
              ))}
              {history.length === 0 && <tr><td colSpan={9} className="empty">Hozircha bitimlar yo'q</td></tr>}
            </tbody>
          </table>
        </div>
      </div>

      {toast && <div className={`toast ${toast.includes('Xato') ? 'err' : 'ok'}`}>{toast}</div>}
    </div>
  )
}