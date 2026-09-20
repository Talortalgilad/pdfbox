const EXAMPLES = ['סובב את הכל 90', 'מחק עמודים 2-4', 'השאר רק עמודים 1-3', 'הפוך את סדר העמודים']

export default function Instructions({ value, onChange, disabled }) {
  return (
    <div className="instr">
      <textarea
        rows={3}
        placeholder="לדוגמה: מחק עמוד 1, ואז סובב את הכל 90"
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value)}
      />
      <div className="chips">
        {EXAMPLES.map((ex) => (
          <button key={ex} type="button" disabled={disabled} onClick={() => onChange(value ? `${value}, ${ex}` : ex)}>
            {ex}
          </button>
        ))}
      </div>
    </div>
  )
}
