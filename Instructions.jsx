const EXAMPLES = ['הסר ווטרמארק', 'הסר ווטרמארק אגרסיבי', 'מחק JET MIDWEST', 'מחק עמודים 2-4', 'סובב את הכל 90']

export default function Instructions({ value, onChange, disabled }) {
  return (
    <div className="instr">
      <textarea
        rows={3}
        placeholder="לדוגמה: הסר ווטרמארק, ואז מחק את שם הלקוח JET MIDWEST"
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
