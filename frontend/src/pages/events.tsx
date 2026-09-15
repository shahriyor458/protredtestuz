import { useCallback, useEffect, useState } from 'react'
import { api, EventRow } from '../api'

export default function Events() {
  const [events, setEvents] = useState<EventRow[]>([])

  const load = useCallback(() => {
    api.events(300).then((r) => setEvents(r.events)).catch(() => {})
  }, [])

  useEffect(() => {
    load()
    const t = setInterval(load, 10000)
    return () => clearInterval(t)
  }, [load])

  return (
    <div>
      <div className="page-title">Sistema jurnali</div>
      <div className="card" style={{ padding: '10px 16px' }}>
        {events.length === 0 && <div className="empty">Jurnal bo'sh</div>}
        {events.map((e) => (
          <div key={`${e.ts}-${e.source}-${e.message}`} className={`log-row log-${e.level}`}>
            <span className="log-ts">{new Date(e.ts).toLocaleString()}</span>
            <span className="muted">[{e.source}]</span> {e.message}
          </div>
        ))}
      </div>
    </div>
  )
}