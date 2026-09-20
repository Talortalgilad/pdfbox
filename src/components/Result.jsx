export default function Result({ url, name, onReset }) {
  const outName = name.replace(/\.pdf$/i, '') + '-edited.pdf'
  return (
    <div className="result">
      <iframe title="preview" src={url} />
      <div className="actions">
        <a className="primary" href={url} download={outName}>הורד את הקובץ</a>
        <button type="button" onClick={onReset}>התחל מחדש</button>
      </div>
    </div>
  )
}
