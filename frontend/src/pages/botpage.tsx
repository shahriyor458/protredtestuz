import { useEffect, useState } from 'react'
import { api, BroadcastRow } from '../api'

const TEMPLATES = [
  '📢 <b>Yangi imkoniyat!</b>\nAI Metal Trader endi yangi darajada imkoniyatlarni taqdim etadi.\n/status — o\'z hisobingizni tekshiring!',
  '📊 <b>Kunlik autstaff</b>\nXAU/USD va XAG/USD bo\'yicha eng so\'nggi AI signallarini kuzating.\n/risk — xavf limitlaringizni sozlang.',
]

export default function BotPage() {
  const [text, setText] = useState('')
  const [history, setHistory] = useState<BroadcastRow[]>([])
  const [sending, setSending] = useState(false)
  const [toast, setToast] = useState<{ ok: boolean; msg: string } | null>(null)
  const [confirm, setConfirm] = useState(false)

  const load = () => api.adminBroadcasts().then((r) => setHistory(r.broadcasts)).catch(() => {})
  useEffect(() => { load() }, [])

  const toastMsg = (ok: boolean, msg: string) => {
    setToast({ ok, msg })
    setTimeout(() => setToast(null), 5000)
  }

  const send = async () => {
    if (!text.trim()) return
    setSending(true)
    try {
      const r = await api.sendBroadcast(text)
      setConfirm(false)
      setText('')
      load()
      toastMsg(true, `Yuborildi: ${r.sent} ta chat`)
    } catch (e) {
      toastMsg(false, String(e))
    } finally {
      setSending(false)
    }
  }

  return (
    <div>
      <div className="page-title">
        Bot Sahifasi — Telegram Reklama
        <span className="muted" style={{ fontSize: 13 }}>Barcha ulangan chatlarga bir vaqtda yuborish</span>
      </div>

      <div className="card section">
        <h3>Reklama / xabar matni</h3>
        <div className="flex" style={{ marginBottom: 10 }}>
          {TEMPLATES.map((t, i) => (
            <button key={i} className="btn" onClick={() => setText(t)}>Shablon {i + 1}</button>
          ))}
          <button className="btn" onClick={() => setText('')}>Tozalash</button>
        </div>
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={6}
          style={{ width: '100%', fontFamily: 'var(--mono)', fontSize: 13 }}
          placeholder="Xabarni HTML-formatda yozing (maks ~4000 belgi)..."
        />
        <div className="flex" style={{ marginTop: 12 }}>
          <button
            className="btn btn-ok"
            disabled={sending || !text.trim()}
            onClick={() => setConfirm(true)}
          >
            {sending ? 'Yuborilmoqda...' : '📤 Reklamani yuborish'}
          </button>
          <span className="muted" style={{ fontSize: 12 }}>
            ⚠️ Butun Telegram auditoriyaga yuboriladi (barcha ulangan chatlar).
          </span>
        </div>
      </div>

      {confirm && (
        <div className="card section" style={{ borderColor: 'var(--amber)' }}>
          <b>Tasdiqlash:</b> Reklama barcha ulangan chatlarga yuboriladi. Davom etasizmi?
          <div className="flex" style={{ marginTop: 10 }}>
            <button className="btn btn-danger" onClick={() => setConfirm(false)}>Bekor qilish</button>
            <button className="btn btn-ok" onClick={send} disabled={sending}>Ha, yuborish</button>
          </div>
        </div>
      )}

      {toast && <div className={`toast ${toast.ok ? 'ok' : 'err'}`}>{toast.msg}</div>}

      <div className="section-head">
        <h2>Tarix</h2>
      </div>
      <div className="card">
        {history.length === 0 ? (
          <div className="empty" style={{ padding: 20 }}>Hali reklama yuborilmagan.</div>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>#</th>
                <th>Xabar</th>
                <th>Olib borganlar</th>
                <th>Sana</th>
              </tr>
            </thead>
            <tbody>
              {history.map((b) => (
                <tr key={b.id}>
                  <td className="mono muted">{b.id}</td>
                  <td style={{ maxWidth: 520 }}>{b.text.slice(0, 140)}{b.text.length > 140 ? '...' : ''}</td>
                  <td>{b.recipients} ta</td>
                  <td className="mono muted" style={{ fontSize: 12 }}>{b.created_at ? b.created_at.slice(0, 16).replace('T', ' ') : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}