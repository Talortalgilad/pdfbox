import { PDFDocument, degrees } from 'pdf-lib'

export async function applyOps(fileBytes, ops) {
  let doc = await PDFDocument.load(fileBytes)

  for (const op of ops) {
    const count = doc.getPageCount()
    if (op.type === 'rotate') {
      const targets = op.pages.length ? op.pages : Array.from({ length: count }, (_, i) => i + 1)
      for (const n of targets) {
        if (n >= 1 && n <= count) {
          const page = doc.getPage(n - 1)
          page.setRotation(degrees(page.getRotation().angle + op.degrees))
        }
      }
    } else if (op.type === 'delete') {
      const toDelete = [...new Set(op.pages)].filter((n) => n >= 1 && n <= count).sort((a, b) => b - a)
      for (const n of toDelete) doc.removePage(n - 1)
    } else if (op.type === 'keep' || op.type === 'reverse') {
      const order =
        op.type === 'reverse'
          ? Array.from({ length: count }, (_, i) => count - 1 - i)
          : [...new Set(op.pages)].filter((n) => n >= 1 && n <= count).map((n) => n - 1)
      const next = await PDFDocument.create()
      const copied = await next.copyPages(doc, order)
      copied.forEach((p) => next.addPage(p))
      doc = next
    }
  }

  return doc.save()
}
