// מפרש הוראות בעברית/אנגלית לפקודות מובנות.
// בהמשך אפשר להחליף את זה בקריאה למודל שפה.

const toNums = (s) => s.match(/\d+/g)?.map(Number) || []

function parsePages(text) {
  const range = text.match(/(\d+)\s*(?:-|עד|to)\s*(\d+)/)
  if (range) {
    const [a, b] = [Number(range[1]), Number(range[2])]
    const out = []
    for (let i = Math.min(a, b); i <= Math.max(a, b); i++) out.push(i)
    return out
  }
  return toNums(text)
}

export function parseInstructions(text) {
  const ops = []
  const parts = text.split(/[,\n;]| ואז | וגם /).map((p) => p.trim()).filter(Boolean)

  for (const p of parts) {
    if (/סובב|rotate/i.test(p)) {
      const deg = toNums(p).find((n) => [90, 180, 270].includes(n)) || 90
      const pages = /את הכל|כל העמודים|all/i.test(p) ? [] : toNums(p).filter((n) => ![90, 180, 270].includes(n))
      ops.push({ type: 'rotate', degrees: deg, pages })
    } else if (/מחק|הסר|delete|remove/i.test(p)) {
      ops.push({ type: 'delete', pages: parsePages(p) })
    } else if (/השאר|רק|keep|only|extract|חלץ/i.test(p)) {
      ops.push({ type: 'keep', pages: parsePages(p) })
    } else if (/הפוך את הסדר|סדר הפוך|reverse/i.test(p)) {
      ops.push({ type: 'reverse' })
    } else {
      ops.push({ type: 'unknown', text: p })
    }
  }
  return ops
}

export function describeOp(op) {
  switch (op.type) {
    case 'rotate':
      return `סיבוב ${op.degrees}° ${op.pages.length ? 'בעמודים ' + op.pages.join(', ') : 'בכל העמודים'}`
    case 'delete':
      return `מחיקת עמודים ${op.pages.join(', ')}`
    case 'keep':
      return `השארת עמודים ${op.pages.join(', ')} בלבד`
    case 'reverse':
      return 'היפוך סדר העמודים'
    default:
      return `לא הבנתי: "${op.text}"`
  }
}
