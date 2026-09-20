import { useState } from 'react'
import Dropzone from './components/Dropzone.jsx'
import Instructions from './components/Instructions.jsx'
import Result from './components/Result.jsx'
import { parseInstructions, describeOp } from './lib/parseInstructions.js'
import { applyOps } from './lib/applyOps.js'

export default function App() {
  const [file, setFile] = useState(null)
  const [text, setText] = useState('')
  const [ops, setOps] = useState([])
  const [status, setStatus] = useState('idle') // idle | working | done | error
  const [resultUrl, setResultUrl] = useState(null)
  const [error, setError] = useState('')

  const onText = (t) => {
    setText(t)
    setOps(t.trim() ? parseInstructions(t) : [])
  }

  const run = async () => {
    const valid = ops.filter((o) => o.type !== 'unknown')
    if (!file || !valid.length) return
    setStatus('working')
    setError('')
    try {
      const bytes = await file.arrayBuffer()
      const out = await applyOps(bytes, valid)
      const blob = new Blob([out], { type: 'application/pdf' })
      if (resultUrl) URL.revokeObjectURL(resultUrl)
      setResultUrl(URL.createObjectURL(blob))
      setStatus('done')
    } catch (e) {
      setError(e.message || 'משהו השתבש בעיבוד הקובץ')
      setStatus('error')
    }
  }

  const reset = () => {
    setFile(null); setText(''); setOps([]); setStatus('idle'); setResultUrl(null); setError('')
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
        <Instructions value={text} onChange={onText} disabled={!file} />
        {ops.length > 0 && (
          <ul className="plan">
            {ops.map((op, i) => (
              <li key={i} className={op.type === 'unknown' ? 'bad' : ''}>{describeOp(op)}</li>
            ))}
          </ul>
        )}
        <button
          className="primary"
          onClick={run}
          disabled={!file || !ops.some((o) => o.type !== 'unknown') || status === 'working'}
        >
          {status === 'working' ? 'מעבד…' : 'בצע עריכה'}
        </button>
        {error && <p className="error">{error}</p>}
      </section>

      {status === 'done' && (
        <section className="step">
          <h2>3. התוצאה</h2>
          <Result url={resultUrl} name={file.name} onReset={reset} />
        </section>
      )}
    </main>
  )
}
