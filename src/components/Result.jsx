export default function Result({ url, name, kind = 'pdf', onReset }) {
  const base = name.replace(/\.pdf$/i, '')
  const outName = kind === 'xlsx' ? base + '.xlsx' : base + '-edited.pdf'
  return (
    <div className="result">
      {kind === 'pdf'
        ? <iframe title="preview" src={url} />
        : <p className="muted">נוצר קובץ Excel. הורד אותו כדי לצפות.</p>}
      <div className="actions">
        <a className="primary" href={url} download={outName}>{kind === 'xlsx' ? 'הורד את האקסל' : 'הורד את הקובץ'}</a>
        <button type="button" onClick={onReset}>התחל מחדש</button>
      </div>
    </div>
  )
}
