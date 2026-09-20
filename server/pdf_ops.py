"""פעולות עריכה על PDF — רץ בשרת. תומך גם בקבצים סרוקים (תמונה) וגם בקבצי טקסט."""
import io
import re
import numpy as np
import pymupdf
import pytesseract
from PIL import Image

OCR_DPI = 200


# ---------- כלי עזר ----------

def is_scanned(page) -> bool:
    """עמוד נחשב 'סרוק' אם תמונה אחת מכסה את רוב שטחו — גם אם יש שכבת OCR מעליה."""
    area = page.rect.get_area()
    if area <= 0:
        return False
    for info in page.get_image_info():
        r = pymupdf.Rect(info["bbox"])
        if r.get_area() / area > 0.5:
            return True
    return len(page.get_text().strip()) == 0 and len(page.get_images()) > 0


def page_image(page, dpi=OCR_DPI) -> Image.Image:
    pix = page.get_pixmap(dpi=dpi)
    return Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")


def replace_page_with_image(doc, page_index, img: Image.Image):
    """מחליף עמוד בתמונה (משמש אחרי עיבוד פיקסלים)."""
    old = doc[page_index]
    rect = old.rect
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=88)
    doc.delete_page(page_index)
    new = doc.new_page(page_index, width=rect.width, height=rect.height)
    new.insert_image(rect, stream=buf.getvalue())


# ---------- 1. מחיקת טקסט (OCR או שכבת טקסט) ----------

def ocr_find(img: Image.Image, phrase: str):
    """מחזיר רשימת מלבנים (בפיקסלים) שבהם מופיע הביטוי."""
    words = [w for w in phrase.upper().split() if w]
    data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
    txt = [t.upper().strip(".,:;") for t in data["text"]]
    hits = []
    n = len(words)
    for i in range(len(txt) - n + 1):
        if txt[i:i + n] == words:
            xs = [data["left"][j] for j in range(i, i + n)]
            ys = [data["top"][j] for j in range(i, i + n)]
            xe = [data["left"][j] + data["width"][j] for j in range(i, i + n)]
            ye = [data["top"][j] + data["height"][j] for j in range(i, i + n)]
            hits.append((min(xs), min(ys), max(xe), max(ye)))
    return hits


def redact_text(doc, phrase: str, pages=None) -> int:
    """מוחק ביטוי מהמסמך. מחזיר כמה מופעים נמחקו."""
    count = 0
    scale = 72 / OCR_DPI
    for i, page in enumerate(doc):
        if pages and (i + 1) not in pages:
            continue
        if is_scanned(page):
            img = page_image(page)
            for x0, y0, x1, y1 in ocr_find(img, phrase):
                r = pymupdf.Rect(x0 * scale - 3, y0 * scale - 3, x1 * scale + 3, y1 * scale + 3)
                page.add_redact_annot(r, fill=(1, 1, 1))
                count += 1
            if count:
                page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_PIXELS)
        else:
            for r in page.search_for(phrase):
                page.add_redact_annot(r, fill=(1, 1, 1))
                count += 1
            page.apply_redactions()
    return count


# ---------- 2. הסרת ווטרמארק ----------

def remove_watermark_pixels(img: Image.Image, text_dark=100, keep_gray_below=None) -> Image.Image:
    """
    לסריקות: משאיר רק פיקסלים כהים (טקסט/קווים/חתימות) ומלבין כל השאר.
    ווטרמארק ברוב המקרים בהיר או צבעוני, ולכן נעלם. טקסט שחור שמעליו נשמר.
    """
    a = np.asarray(img).astype(np.int16)
    mn = a.min(axis=2)          # הערוץ הכהה ביותר
    mx = a.max(axis=2)
    sat = mx - mn               # "צבעוניות"
    dark = mn < text_dark       # כהה מספיק להיות דיו
    colored = sat > 60          # אדום/כחול/ירוק — ווטרמארק צבעוני
    keep = dark & ~colored
    # חתימות בעט כחול: כהות + צבעוניות בינונית — נשמור רק אם ממש כהות
    keep |= (mn < 35) & (sat < 120)
    # ניקוי פיקסלים בודדים שנשארו (רעש JPEG סביב ווטרמארק)
    k = keep.astype(np.uint8)
    nb = np.zeros_like(k, dtype=np.int16)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dy or dx:
                nb += np.roll(np.roll(k, dy, 0), dx, 1)
    keep &= nb >= 2
    out = np.where(keep[..., None], a, 255).astype(np.uint8)
    return Image.fromarray(out)


def remove_watermark_vector(page, text_hint: str | None = None) -> int:
    """
    לקבצי טקסט: מוחק הערות מסוג Watermark/Stamp, טקסט מסובב, וטקסט לפי רמז.
    """
    removed = 0
    for annot in list(page.annots() or []):
        if annot.type[1] in ("Watermark", "Stamp", "FreeText"):
            page.delete_annot(annot)
            removed += 1
    rects = []
    if text_hint:
        rects += page.search_for(text_hint)
    d = page.get_text("dict")
    for block in d.get("blocks", []):
        for line in block.get("lines", []):
            dx, dy = line.get("dir", (1, 0))
            rotated = abs(dy) > 0.2
            for span in line.get("spans", []):
                big = span.get("size", 0) >= 40
                if rotated or big:
                    rects.append(pymupdf.Rect(span["bbox"]))
    for r in rects:
        page.add_redact_annot(r, fill=(1, 1, 1))
    if rects:
        page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE)
        removed += len(rects)
    return removed


def remove_watermark(doc, text_hint: str | None = None, force_pixels: bool = False) -> int:
    touched = 0
    for i in range(len(doc)):
        page = doc[i]
        removed = 0
        if not force_pixels and not is_scanned(page):
            removed = remove_watermark_vector(page, text_hint)
            page = doc[i]
        if force_pixels or is_scanned(page) or removed == 0:
            # מסלול פיקסלים: הופך את העמוד לתמונה ומנקה. עובד על כל סוג קובץ.
            img = page_image(page)
            if text_hint:
                # אם יש רמז, נלבין גם את האזורים שה-OCR מצא (לווטרמארק שחור)
                scale_px = 1
                for x0, y0, x1, y1 in ocr_find(img, text_hint):
                    a = np.asarray(img).copy()
                    a[max(0, y0 - 4):y1 + 4, max(0, x0 - 4):x1 + 4] = 255
                    img = Image.fromarray(a)
            clean = remove_watermark_pixels(img)
            replace_page_with_image(doc, i, clean)
            removed = 1
        touched += removed
    return touched


# ---------- 3. פעולות עמודים ----------

def rotate(doc, degrees, pages=None):
    for i, p in enumerate(doc):
        if not pages or (i + 1) in pages:
            p.set_rotation((p.rotation + degrees) % 360)


def delete_pages(doc, pages):
    idx = sorted({p - 1 for p in pages if 1 <= p <= len(doc)}, reverse=True)
    for i in idx:
        doc.delete_page(i)


def keep_pages(doc, pages):
    idx = [p - 1 for p in pages if 1 <= p <= len(doc)]
    doc.select(idx)


def reverse(doc):
    doc.select(list(range(len(doc) - 1, -1, -1)))


# ---------- 4. פרשן הוראות (עברית/אנגלית) ----------

def _pages(text):
    m = re.search(r"(\d+)\s*(?:-|עד|to)\s*(\d+)", text)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        return list(range(min(a, b), max(a, b) + 1))
    return [int(n) for n in re.findall(r"\d+", text)]


def parse(text: str):
    ops = []
    parts = [p.strip() for p in re.split(r"[\n;]| ואז | וגם ", text) if p.strip()]
    for p in parts:
        low = p.lower()
        if re.search(r"הצלב|הצלבה|מבוקש|wanted|match|cross", low):
            ops.append({"type": "match"})
        elif re.search(r"חלץ|חילוץ|לחלץ|extract|אקסל|excel|טבלה|מניפסט|manifest", low):
            m = re.search(r"(?:עמודות|columns)\s*[:]?\s*(.+)$", p, re.I)
            ops.append({"type": "extract", "hint": m.group(1).strip() if m else None})
        elif re.search(r"ווטרמארק|ווטר מארק|סימן מים|watermark", low):
            m = re.search(r"(?:כתוב|שכתוב|בו|text)\s*[:\"']?\s*(.+)$", p)
            force = bool(re.search(r"אגרסיבי|חזק|בכוח|force|hard", low))
            ops.append({"type": "watermark", "hint": m.group(1).strip(" \"'") if m else None, "force": force})
        elif re.search(r"סובב|rotate", low):
            nums = [int(n) for n in re.findall(r"\d+", p)]
            deg = next((n for n in nums if n in (90, 180, 270)), 90)
            pages = [] if re.search(r"הכל|כל העמודים|all", low) else [n for n in nums if n not in (90, 180, 270)]
            ops.append({"type": "rotate", "degrees": deg, "pages": pages})
        elif re.search(r"(מחק|תמחק|הסר|תסיר|delete|remove)\s+(את\s+)?(ה)?עמוד", low):
            ops.append({"type": "delete", "pages": _pages(p)})
        elif re.search(r"השאר|תשאיר|רק עמוד|keep|only", low):
            ops.append({"type": "keep", "pages": _pages(p)})
        elif re.search(r"הפוך את הסדר|סדר הפוך|reverse", low):
            ops.append({"type": "reverse"})
        elif re.search(r"מחק|תמחק|הסר|תסיר|delete|remove|redact", low):
            m = re.search(r"(?:מחק|תמחק|הסר|תסיר|delete|remove|redact)\s+(?:את\s+)?(?:ה?טקסט\s+|ה?מילה\s+|ה?מילים\s+)?[\"']?(.+?)[\"']?\s*$", p, re.I)
            phrase = m.group(1).strip() if m else ""
            # "מחק את שם הלקוח JET MIDWEST" -> ניקח את החלק באנגלית/מספרים אם יש
            latin = re.findall(r"[A-Za-z0-9][A-Za-z0-9 .&\-/]*", phrase)
            if latin and re.search(r"[\u0590-\u05FF]", phrase):
                phrase = max(latin, key=len).strip()
            ops.append({"type": "redact", "text": phrase})
        else:
            ops.append({"type": "unknown", "text": p})
    return ops


def describe(op):
    t = op["type"]
    if t == "match":
        return "חילוץ טבלה והצלבה מול רשימת המבוקשים של הוק"
    if t == "extract":
        return "חילוץ טבלה לאקסל" + (f' (עמודות: {op["hint"]})' if op.get("hint") else "")
    if t == "watermark":
        return "הסרת ווטרמארק" + (" (אגרסיבי)" if op.get("force") else "") + (f' ("{op["hint"]}")' if op.get("hint") else "")
    if t == "redact":
        return f'מחיקת הטקסט "{op["text"]}"'
    if t == "rotate":
        pg = "בעמודים " + ", ".join(map(str, op["pages"])) if op["pages"] else "בכל העמודים"
        return f'סיבוב {op["degrees"]}° {pg}'
    if t == "delete":
        return "מחיקת עמודים " + ", ".join(map(str, op["pages"]))
    if t == "keep":
        return "השארת עמודים " + ", ".join(map(str, op["pages"])) + " בלבד"
    if t == "reverse":
        return "היפוך סדר העמודים"
    return f'לא הבנתי: "{op["text"]}"'


def apply(pdf_bytes: bytes, ops):
    """מחזיר (bytes, log, kind) — kind הוא 'pdf' או 'xlsx'."""
    from . import extract as _extract
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    log = []
    for op in ops:
        t = op["type"]
        if t == "match":
            from . import wanted as _wanted
            out, msg = _extract.extract_tables(doc, None)
            doc.close()
            if out is None:
                raise ValueError(msg)
            out, msg2 = _wanted.match_workbook(out, "uploaded PDF")
            log += [msg, msg2]
            return out, log, "xlsx"
        if t == "extract":
            # חילוץ מסיים את השרשרת — הפלט הוא אקסל (אחרי כל פעולות העמודים שקדמו לו)
            out, msg = _extract.extract_tables(doc, op.get("hint"))
            log.append(msg)
            doc.close()
            if out is None:
                raise ValueError(msg)
            return out, log, "xlsx"
        if t == "watermark":
            n = remove_watermark(doc, op.get("hint"), op.get("force", False))
            log.append(f"ווטרמארק: טופלו {n} עמודים/אלמנטים")
        elif t == "redact":
            n = redact_text(doc, op["text"])
            log.append(f'"{op["text"]}": נמחקו {n} מופעים' if n else f'"{op["text"]}": לא נמצא בקובץ')
        elif t == "rotate":
            rotate(doc, op["degrees"], op["pages"]); log.append(describe(op))
        elif t == "delete":
            delete_pages(doc, op["pages"]); log.append(describe(op))
        elif t == "keep":
            keep_pages(doc, op["pages"]); log.append(describe(op))
        elif t == "reverse":
            reverse(doc); log.append(describe(op))
    out = doc.tobytes(garbage=3, deflate=True)
    doc.close()
    return out, log, "pdf"
