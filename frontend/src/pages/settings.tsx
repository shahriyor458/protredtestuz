import { useCallback, useEffect, useState } from 'react'
import { api, AccountRow, getToken, RiskSettings, Status } from '../api'

const RISK_DESC: Record<string, string> = {
  conservative: 'Past — har bir bitimga 1–2%',
  moderate: "O'rta — har bir bitimga 3–5%",
  aggressive: 'Yuqori — har bir bitimga 5%+',
}

export default function Settings({ status }: { status: Status | null }) {
  const [risk, setRisk] = useState<RiskSettings | null>(null)
  const [accounts, setAccounts] = useState<AccountRow[]>([])
  const [saving, setSaving] = useState(false)
  const [toast, setToast] = useState<string | null>(null)
  const [newAccName, setNewAccName] = useState('')
  const [selected, setSelected] = useState('moderate')

  const [form, setForm] = useState({
    max_risk_per_trade: 3,
    max_daily_drawdown: 5,
    daily_profit_target: 20,
    max_open_positions: 4,
    min_confidence: 70,
    max_daily_trades: 6,
    paper_trading: true,
    scalping: true,
    news_trading: true,
  })

  const load = useCallback(async () => {
    try {
      const [r, a] = await Promise.all([api.settings(), api.accounts()])
      setRisk(r)
      setSelected(r.risk_level)
      setForm({
        max_risk_per_trade: r.max_risk_per_trade,
        max_daily_drawdown: r.max_daily_drawdown,
        daily_profit_target: r.daily_profit_target,
        max_open_positions: r.max_open_positions,
        min_confidence: r.min_confidence,
        max_daily_trades: r.max_daily_trades,
        paper_trading: r.paper_trading,
        scalping: r.scalping !== undefined ? r.scalping : true,
        news_trading: r.news_trading !== undefined ? r.news_trading : true,
      })
      setAccounts(a.accounts)
    } catch { /* ignore */ }
  }, [])

  useEffect(() => { load() }, [load])
  const toastMsg = (msg: string, err = false) => {
    setToast(err ? `⚠️ ${msg}` : msg)
    setTimeout(() => setToast(null), 3500)
  }

  const saveRisk = async (body: Record<string, unknown>) => {
    setSaving(true)
    try {
      const res = await api.updateSettings(body)
      setRisk(res.settings)
      setSelected(res.settings.risk_level)
      toastMsg('Limitlar saqlandi')
      load()
    } catch (e) {
      toastMsg(`Xato: ${(e as Error).message}`, true)
    } finally {
      setSaving(false)
    }
  }

  const applyLevel = (level: string) => {
    const band: Record<string, [number, number]> = {
      conservative: [1, 2],
      moderate: [3, 5],
      aggressive: [5, 8],
    }
    const [, hi] = band[level]
    setSelected(level)
    setForm((f) => ({ ...f, max_risk_per_trade: hi }))
    saveRisk({ risk_level: level, max_risk_per_trade: hi })
  }

  const createAccount = async () => {
    try {
      const res = await api.createAccount(newAccName)
      toastMsg(`✅ Yangi akkaunt: kod ${res.account.link_code}`)
      setNewAccName('')
      load()
    } catch (e) {
      toastMsg(`Xato: ${(e as Error).message}`, true)
    }
  }

  const testTelegram = async () => {
    try {
      const r = await api.telegramTest('✅ Test — Pro Tred AI bot ishlayapti!')
      toastMsg(`Telegram ga yuborildi: ${r.sent_to.join(', ') || "ulangan chat yo'q"}`)
    } catch (e) {
      toastMsg(`Xato: ${(e as Error).message}`, true)
    }
  }

  const sendReport = async () => {
    try {
      await api.sendReport()
      toastMsg('Kunlik hisobot yuborildi')
    } catch (e) {
      toastMsg(`Xato: ${(e as Error).message}`, true)
    }
  }

  return (
    <div>
      <div className="page-title">Sozlamalar va Akkauntlar</div>

      {/* Risk darajalari */}
      <div className="section">
        <div className="section-head"><h2>Xavf darajasi (Risk Level)</h2><span className="muted">Manual Risk Setter</span></div>
        <div className="flex" style={{ marginBottom: 16 }}>
          {Object.entries(RISK_DESC).map(([lv, desc]) => (
            <button
              key={lv}
              className={`btn ${selected === lv ? 'btn-ok' : ''}`}
              onClick={() => applyLevel(lv)}
            >
              {lv.toUpperCase()}
              <span className="muted" style={{ fontSize: 11 }}>{desc}</span>
            </button>
          ))}
        </div>

        <div className="card section">
          <h3>Qo'lda limitlar</h3>
          <div className="grid grid-3">
            <div className="field">
              <label>Max risk / bitimga (%)</label>
              <input type="number" step="0.1" min="0.5" max="15"
                value={form.max_risk_per_trade}
                onChange={(e) => setForm({ ...form, max_risk_per_trade: Number(e.target.value) })}
                onBlur={() => saveRisk({ max_risk_per_trade: form.max_risk_per_trade })} />
            </div>
            <div className="field">
              <label>Max kunlik stop-loss (Drawdown %)</label>
              <input type="number" step="0.5" min="0.5" max="50"
                value={form.max_daily_drawdown}
                onChange={(e) => setForm({ ...form, max_daily_drawdown: Number(e.target.value) })}
                onBlur={() => saveRisk({ max_daily_drawdown: form.max_daily_drawdown })} />
            </div>
            <div className="field">
              <label>Kunlik foyda maqsadi (%)</label>
              <input type="number" step="1" min="1" max="200"
                value={form.daily_profit_target}
                onChange={(e) => setForm({ ...form, daily_profit_target: Number(e.target.value) })}
                onBlur={() => saveRisk({ daily_profit_target: form.daily_profit_target })} />
            </div>
            <div className="field">
              <label>Maks ochiq pozitsiya</label>
              <input type="number" step="1" min="1" max="30"
                value={form.max_open_positions}
                onChange={(e) => setForm({ ...form, max_open_positions: Number(e.target.value) })}
                onBlur={() => saveRisk({ max_open_positions: form.max_open_positions })} />
            </div>
            <div className="field">
              <label>Min signal confidence (%)</label>
              <input type="number" step="1" min="0" max="100"
                value={form.min_confidence}
                onChange={(e) => setForm({ ...form, min_confidence: Number(e.target.value) })}
                onBlur={() => saveRisk({ min_confidence: form.min_confidence })} />
            </div>
            <div className="field">
              <label>Kunlik savdo limiti (bitim)</label>
              <input type="number" step="1" min="1" max="100"
                value={form.max_daily_trades}
                onChange={(e) => setForm({ ...form, max_daily_trades: Number(e.target.value) })}
                onBlur={() => saveRisk({ max_daily_trades: form.max_daily_trades })} />
            </div>
          </div>
          <label className="flex" style={{ gap: 8, cursor: 'pointer' }}>
            <input type="checkbox"
              checked={form.paper_trading}
              onChange={(e) => { setForm({ ...form, paper_trading: e.target.checked }); saveRisk({ paper_trading: e.target.checked }) }}
              style={{ width: 'auto' }} />
            <b>{form.paper_trading ? '🧪 PAPER (demo) rejim' : '🔴 REAL savdo rejim'}</b>
          </label>
          <div className="flex" style={{ gap: 20, marginTop: 10 }}>
            <label className="flex" style={{ gap: 8, cursor: 'pointer' }}>
              <input type="checkbox"
                checked={form.scalping}
                onChange={(e) => { setForm({ ...form, scalping: e.target.checked }); saveRisk({ scalping: e.target.checked }) }}
                style={{ width: 'auto' }} />
              <b>{form.scalping ? '⚡ SCALPING (razgon) — tezkor savdo' : '⚡ Scalping o\'chirilgan'}</b>
            </label>
            <label className="flex" style={{ gap: 8, cursor: 'pointer' }}>
              <input type="checkbox"
                checked={form.news_trading}
                onChange={(e) => { setForm({ ...form, news_trading: e.target.checked }); saveRisk({ news_trading: e.target.checked }) }}
                style={{ width: 'auto' }} />
              <b>{form.news_trading ? '📰 YANGILIKLAR asosida savdo' : '📰 Yangiliklar savdosi o\'chirilgan'}</b>
            </label>
          </div>
          {saving && <div className="muted" style={{ marginTop: 8 }}>Saqlanmoqda...</div>}
        </div>
      </div>

      {/* Telegram */}
      <div className="section">
        <div className="section-head"><h2>Telegram Bot Ulash</h2></div>
        <div className="card">
          <p className="muted" style={{ marginBottom: 12 }}>
            Akkauntni Telegram botga ulash uchun: admin panelda akkaunt yarating → chiqqan{' '}
            <b>5 xonali kod</b>ni Telegram botga <b>/link 12345</b> ko'rinishida yuboring.
            Kunlik hisobot, bitim ogohlantirishlari va risklar shu chatga keladi.
          </p>
          <div className="flex">
            <button className="btn btn-ok" onClick={testTelegram}>🧪 Test xabar</button>
            <button className="btn" onClick={sendReport}>📈 Kunlik hisobotni yuborish</button>
            <span className="muted" style={{ fontSize: 12 }}>
              Bot tokeni: <code className="gold">{getToken() ? '<backend/.env> TELEGRAM_BOT_TOKEN' : 'sozlanmagan'}</code>
            </span>
          </div>
        </div>

        <div className="card" style={{ marginTop: 14 }}>
          <h3>Telegram-o'tkazma akkauntlar (5 xonali ID)</h3>
          <div className="flex" style={{ marginBottom: 12 }}>
            <input
              style={{ maxWidth: 220 }}
              placeholder="Akkaunt nomi (ixtiyoriy)"
              value={newAccName}
              onChange={(e) => setNewAccName(e.target.value)}
            />
            <button className="btn btn-ok" onClick={createAccount}>+ Yangi akkaunt yaratish</button>
          </div>
          <table className="table">
            <thead>
              <tr><th>ID</th><th>Nomi</th><th>Link kod</th><th>Holat</th><th>Telegram</th></tr>
            </thead>
            <tbody>
              {accounts.map((a) => (
                <tr key={a.id}>
                  <td className="muted mono">{a.id}</td>
                  <td>{a.name || '—'}</td>
                  <td><span className="badge-code">{a.link_code}</span></td>
                  <td>{a.linked
                    ? <span className="tag tag-open">✅ Ulangan</span>
                    : <span className="tag tag-closed">Ulash kutilmoqda</span>}</td>
                  <td className="muted">{a.tg_username ? `@${a.tg_username}` : '—'}</td>
                </tr>
              ))}
              {accounts.length === 0 && <tr><td colSpan={5} className="empty">Akkaunt hali yo'q — yuqoridan yarating</td></tr>}
            </tbody>
          </table>
        </div>
      </div>

      {/* Status card */}
      {risk && (
        <div className="card">
          <h3>Joriy hisob (o'qish rejimi)</h3>
          <div className="muted" style={{ lineHeight: 2 }}>
            Broker: <b style={{ color: 'var(--txt)' }}>{status?.account?.broker}</b> · Login #<b style={{ color: 'var(--txt)' }}>{status?.account?.login}</b> · Server {status?.account?.server}<br />
            Balans: <b style={{ color: 'var(--gold)' }}>{status?.account ? status.account.balance.toLocaleString() : '—'} {status?.account?.currency}</b> · Ochiq: {status?.unrealized.open_count}<br />
            Kunlik P&amp;L: {risk.daily_profit_pct}% · Drawdown: {risk.current_drawdown_pct}%
          </div>
        </div>
      )}

      {toast && <div className={`toast ${toast.includes('Xato') ? 'err' : 'ok'}`}>{toast}</div>}
    </div>
  )
}