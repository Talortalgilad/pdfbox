import { useState, useEffect } from 'react'
import Dropzone from './components/Dropzone.jsx'
import Instructions from './components/Instructions.jsx'
import Result from './components/Result.jsx'
import WantedList from './components/WantedList.jsx'

export default function App() {
  const [file, setFile] = useState(null)
  const [text, setText] = useState('')
  const [plan, setPlan] = useState({ ops: [], descriptions: [] })
  const [status, setStatus] = useState('idle') // idle | working | done | error
  const [resultUrl, setResultUrl] = useState(null)
  const [resultKind, setResultKind] = useState('pdf')
  const [log, setLog] = useState([])
  const [error, setError] = useState('')

  // מבקשים מהשרת לפרש את ההוראות (עם השהיה קצרה בזמן הקלדה)
  useEffect(() => {
    if (!text.trim()) { setPlan({ ops: [], descriptions: [] }); return }
    const t = setTimeout(async () => {
      const fd = new FormData(); fd.append('text', text)
      try {
        const r = await fetch('/api/plan', { method: 'POST', body: fd })
        setPlan(await r.json())
      } catch { /* השרת לא זמין — נשאיר את התוכנית ריקה */ }
    }, 300)
    return () => clearTimeout(t)
  }, [text])

  const validOps = plan.ops.filter((o) => o.type !== 'unknown')

  const run = async () => {
    if (!file || !validOps.length) return
    setStatus('working'); setError(''); setLog([])
    try {
      const fd = new FormData()
      fd.append('file', file)
      fd.append('ops', JSON.stringify(validOps))
      const r = await fetch('/api/process', { method: 'POST', body: fd })
      if (!r.ok) {
        const j = await r.json().catch(() => ({}))
        throw new Error(j.error || 'השרת החזיר שגיאה')
      }
      const blob = await r.blob()
      if (resultUrl) URL.revokeObjectURL(resultUrl)
      setResultUrl(URL.createObjectURL(blob))
      setResultKind(r.headers.get('X-Kind') || 'pdf')
      try { setLog(JSON.parse(decodeURIComponent(escape(atob(r.headers.get('X-Log') || 'W10='))))) } catch { setLog([]) }
      setStatus('done')
    } catch (e) {
      setError(e.message || 'משהו השתבש בעיבוד הקובץ')
      setStatus('error')
    }
  }

  const reset = () => {
    setFile(null); setText(''); setPlan({ ops: [], descriptions: [] })
    setStatus('idle'); setResultUrl(null); setLog([]); setError('')
  }

  return (
    <main className="app">
      <header className="hero">
        <h1>PDF Toolbox</h1>
        <p>העלה קובץ, כתוב במילים מה לעשות איתו, וקבל תוצאה.</p>
      </header>

      <section className="step">
        <h2>1. הקובץ</h2>
        <Dropzone file={file} onFile={setFile} />
      </section>

      <section className="step">
        <h2>2. מה לעשות</h2>
        <Instructions value={text} onChange={setText} disabled={!file} />
        <WantedList />
        {plan.descriptions.length > 0 && (
          <ul className="plan">
            {plan.descriptions.map((d, i) => (
              <li key={i} className={plan.ops[i].type === 'unknown' ? 'bad' : ''}>{d}</li>
            ))}
          </ul>
        )}
        <button className="primary" onClick={run} disabled={!file || !validOps.length || status === 'working'}>
          {status === 'working' ? 'מעבד… (סריקות לוקחות כמה שניות)' : 'בצע עריכה'}
        </button>
        {error && <p className="error">{error}</p>}
      </section>

      {status === 'done' && (
        <section className="step">
          <h2>3. התוצאה</h2>
          {log.length > 0 && <ul className="log">{log.map((l, i) => <li key={i}>{l}</li>)}</ul>}
          <Result url={resultUrl} name={file.name} kind={resultKind} onReset={reset} />
        </section>
      )}
    </main>
  )
}
