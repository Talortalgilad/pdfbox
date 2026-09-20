import { useRef, useState } from 'react'

export default function Dropzone({ file, onFile }) {
  const input = useRef()
  const [over, setOver] = useState(false)

  const take = (f) => {
    if (f && f.type === 'application/pdf') onFile(f)
  }

  return (
    <div
      className={`drop ${over ? 'over' : ''} ${file ? 'has' : ''}`}
      onDragOver={(e) => { e.preventDefault(); setOver(true) }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => { e.preventDefault(); setOver(false); take(e.dataTransfer.files[0]) }}
      onClick={() => input.current.click()}
    >
      <input ref={input} type="file" accept="application/pdf" hidden onChange={(e) => take(e.target.files[0])} />
      {file ? (
        <>
          <strong>{file.name}</strong>
          <span>{(file.size / 1024).toFixed(0)} KB · לחץ להחלפה</span>
        </>
      ) : (
        <>
          <strong>גרור לכאן קובץ PDF</strong>
          <span>או לחץ לבחירה מהמחשב</span>
        </>
      )}
    </div>
  )
}
