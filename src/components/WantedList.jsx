import { useEffect, useRef, useState } from 'react'

export default function WantedList() {
  const [count, setCount] = useState(null)
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState('')
  const input = useRef()

  const refresh = () => fetch('/api/wanted').then((r) => r.json()).then((j) => setCount(j.count)).catch(() => {})
  useEffect(() => { refresh() }, [])

  const upload = async (f) => {
    if (!f) return
    setBusy(true); setMsg('')
    const fd = new FormData(); fd.append('file', f)
    try {
      const r = await fetch('/api/wanted', { method: 'POST', body: fd })
      const j = await r.json()
      if (!r.ok) throw new Error(j.error || 'שגיאה')
      setCount(j.count); setMsg('הרשימה עודכנה')
    } catch (e) { setMsg(e.message) }
    setBusy(false)
  }

  return (
    <div className="wanted">
      <span>רשימת מבוקשים בשרת: {count === null ? '…' : `${count.toLocaleString()} מק"טים`}</span>
      <input ref={input} type="file" accept=".xlsx" hidden onChange={(e) => upload(e.target.files[0])} />
      <button type="button" disabled={busy} onClick={() => input.current.click()}>{busy ? 'מעלה…' : 'עדכן רשימה (xlsx)'}</button>
      {msg && <em>{msg}</em>}
    </div>
  )
}
