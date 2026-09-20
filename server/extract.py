"""חילוץ טבלאות מ-PDF (טקסט או סרוק) לקובץ Excel."""
import io
import re
import collections
import pymupdf
import pytesseract
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

OCR_DPI = 300


def _words(page, scanned):
    """מחזיר [(x0,y0,x1,y1,text)] בנקודות PDF."""
    if not scanned:
        return [(w[0], w[1], w[2], w[3], w[4]) for w in page.get_text("words")]
    pix = page.get_pixmap(dpi=OCR_DPI)
    from PIL import Image
    img = Image.open(io.BytesIO(pix.tobytes("png")))
    # סריקות מסובבות (טפסי 8130 לרוחב): מזהים כיוון ומיישרים לפני ה-OCR
    try:
        osd = pytesseract.image_to_osd(img)
        rot = int(re.search(r"Rotate: (\d+)", osd).group(1))
        if rot:
            img = img.rotate(-rot, expand=True)
    except Exception:  # noqa
        pass
    d = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
    s = 72 / OCR_DPI
    out = []
    for i, t in enumerate(d["text"]):
        t = t.strip()
        if t and int(d["conf"][i]) > 30:
            x, y, w, h = d["left"][i] * s, d["top"][i] * s, d["width"][i] * s, d["height"][i] * s
            out.append((x, y, x + w, y + h, t))
    return out


def _is_scanned(page):
    # לחילוץ: אם יש שכבת טקסט סבירה משתמשים בה (גם OCR מובנה עדיף על OCR שלנו)
    return len(page.get_text("words")) < 30


def _lines(words, tol=3.0):
    """מקבץ מילים לשורות לפי y. מחזיר רשימת (y, [words מסודרות לפי x])."""
    words = sorted(words, key=lambda w: (w[1], w[0]))
    lines = []
    for w in words:
        if lines and abs(lines[-1][0] - w[1]) <= tol:
            lines[-1][1].append(w)
        else:
            lines.append([w[1], [w]])
    return [(y, sorted(ws, key=lambda w: w[0])) for y, ws in lines]


def _header_key(ws):
    return " ".join(re.sub(r"[:_.]", "", w[4]).upper() for w in ws)


def _looks_like_header(ws):
    toks = [re.sub(r"[:_.#/()]", "", w[4]) for w in ws]
    toks = [t for t in toks if t]
    if len(toks) < 3:
        return False
    if any(re.search(r"\d", t) for t in toks):   # כותרת טבלה לא מכילה מספרים/קודים
        return False
    caps = sum(1 for t in toks if t.isupper() or t.istitle())
    return caps >= len(toks) * 0.7


def _merge_header(ws, gap=8):
    """מאחד מילות כותרת סמוכות ("SERIAL NUMBER") לעמודה אחת."""
    cols = []
    for w in ws:
        if cols and w[0] - cols[-1][2] < gap:
            x0, y0, x1, y1, t = cols[-1]
            cols[-1] = (x0, min(y0, w[1]), w[2], max(y1, w[3]), t + " " + w[4])
        else:
            cols.append(w)
    return cols


def _bounds(hws, data_lines=None):
    """
    גבולות עמודות. ברירת מחדל: אמצע הרווח בין כותרות סמוכות.
    אם יש שורות נתונים, מחשבים את העמודות מהנתונים עצמם (רווחים אנכיים ריקים)
    ומצמידים כל כותרת לעמודה שמכילה את מרכזה — עובד גם כשהכותרות ממורכזות
    והנתונים מיושרים לשמאל.
    """
    cuts = [0.0] + [(hws[j][2] + hws[j + 1][0]) / 2 for j in range(len(hws) - 1)] + [1e9]
    default = [(cuts[j], cuts[j + 1]) for j in range(len(hws))]
    if not data_lines:
        return default
    lo, hi = hws[0][0] - 60, hws[-1][2] + 80
    spans = [(w[0], w[2]) for _, ws in data_lines
             if all(lo <= w[0] and w[2] <= hi for w in ws) for w in ws]
    if len(spans) < 5:
        return default
    spans.sort()
    cols, cur = [], list(spans[0])
    for a, b in spans[1:]:
        if a - cur[1] > 6:
            cols.append(tuple(cur)); cur = [a, b]
        else:
            cur[1] = max(cur[1], b)
    cols.append(tuple(cur))
    # מרכז כל כותרת → העמודה שמכילה אותו (או הקרובה ביותר)
    # לכל כותרת: העמודה שמכילה את מרכזה; אם אין (עמודה ריקה בנתונים) — טווח הכותרת עצמה
    hcols = []
    for w in hws:
        cx = (w[0] + w[2]) / 2
        hit = next((c for c in cols if c[0] - 3 <= cx <= c[1] + 3), None)
        hcols.append(hit or (w[0], w[2]))
    if any(hcols[j][1] >= hcols[j + 1][0] for j in range(len(hcols) - 1)):
        return default
    out = []
    for j, c in enumerate(hcols):
        left = 0.0 if j == 0 else (hcols[j - 1][1] + c[0]) / 2
        right = 1e9 if j == len(hcols) - 1 else (c[1] + hcols[j + 1][0]) / 2
        out.append((left, right))
    return out


def _table_score(lines, i):
    """כמה השורות שאחרי מועמד-כותרת נראות כמו טבלה שמיושרת לעמודות שלו."""
    hws = _merge_header(lines[i][1])
    if len(hws) < 3:
        return 0
    bounds = _bounds(hws, lines[i + 1:i + 40])
    good = 0
    for _, ws in lines[i + 1:i + 12]:
        cells = [[] for _ in bounds]
        for w in ws:
            for j, (a, b) in enumerate(bounds):
                if a <= w[0] < b:
                    cells[j].append(w[4]); break
        vals = [" ".join(c) for c in cells]
        filled = [v for v in vals if v]
        # שורת טבלה: לפחות 2 תאים, תאים קצרים (לא משפטים), ויש בה מספר/קוד
        if len(filled) >= 2 and all(len(v) <= 35 for v in filled) and vals[0] \
                and any(re.search(r"\d", v) for v in vals):
            good += 1
    return good


def _find_header(pages_lines):
    """בוחר את שורת הכותרת: ניקוד = (בכמה עמודים היא חוזרת) × (כמה השורות אחריה נראות כטבלה)."""
    counter, score = collections.Counter(), collections.Counter()
    for lines in pages_lines:
        seen = set()
        for i, (_, ws) in enumerate(lines):
            if _looks_like_header(ws):
                k = _header_key(ws)
                sc = _table_score(lines, i)
                if sc < 3:
                    continue
                score[k] += sc
                if k not in seen:
                    counter[k] += 1
                    seen.add(k)
    if not counter:
        return None
    return max(counter, key=lambda k: (counter[k] * score[k], score[k]))


def extract_tables(doc, hint=None):
    pages = []
    for i, page in enumerate(doc):
        sc = _is_scanned(page)
        ws = _words(page, sc)
        pages.append((i + 1, _lines(ws), sc))

    header_key = _find_header([l for _, l, _ in pages])
    if hint:
        header_key = None  # הרמז גובר: נחפש שורה שמכילה את כל המילים
    rows, headers, pages_used = [], None, 0

    for pno, lines, sc in pages:
        hidx = None
        for i, (_, ws) in enumerate(lines):
            k = _header_key(ws)
            if hint:
                if all(h.upper() in k for h in re.split(r"[,\s]+", hint) if h):
                    hidx = i; break
            elif header_key and k == header_key:
                hidx = i; break
        if hidx is None:
            continue
        pages_used += 1
        hws = _merge_header(lines[hidx][1])
        if headers is None:
            headers = [re.sub(r"[:]", "", w[4]).strip() for w in hws]
        hh = max(w[3] - w[1] for w in hws)
        bounds = _bounds(hws, lines[hidx + 1:hidx + 60])
        hy = lines[hidx][0]
        lo, hi = hws[0][0] - 60, hws[-1][2] + 80
        for y, ws in lines:
            if y <= hy:
                continue
            if any(w[0] < lo or w[2] > hi for w in ws):   # שורה מחוץ לרוחב הטבלה (כותרת תחתונה וכו')
                continue
            cells = [[] for _ in hws]
            for w in ws:
                if (w[3] - w[1]) > hh * 1.8:      # טקסט ענק = ווטרמארק/כותרת
                    continue
                for j, (a, b) in enumerate(bounds):
                    if a <= w[0] < b:
                        cells[j].append(w[4]); break
            vals = [" ".join(c) for c in cells]
            filled = sum(1 for v in vals if v)
            if filled == 0 or (filled == 1 and not vals[0]):
                continue
            if _looks_like_header(ws):  # כותרת חוזרת / כותרת עליונה
                continue
            rows.append(vals + [pno])

    if not headers:
        return None, "לא נמצאה טבלה עם שורת כותרת ברורה. אפשר לציין: חלץ טבלה עם עמודות PN, DESCRIPTION, QTY"

    wb = Workbook()
    ws_ = wb.active
    ws_.title = "DATA"
    ws_.append(headers + ["PAGE"])
    for r in rows:
        r2 = [int(v) if re.fullmatch(r"\d{1,6}", v) else v for v in r[:-1]] + [r[-1]]
        ws_.append(r2)
    fill = PatternFill("solid", fgColor="1F3A5F")
    for c in ws_[1]:
        c.fill, c.font, c.alignment = fill, Font(name="Arial", bold=True, color="FFFFFF"), Alignment(horizontal="center")
    for row in ws_.iter_rows(min_row=2):
        for c in row:
            c.font = Font(name="Arial", size=10)
    for j in range(1, len(headers) + 2):
        width = max((len(str(ws_.cell(row=r, column=j).value or "")) for r in range(1, min(ws_.max_row, 400) + 1)), default=8)
        ws_.column_dimensions[get_column_letter(j)].width = min(max(8, width + 2), 50)
    ws_.freeze_panes = "A2"
    ws_.auto_filter.ref = f"A1:{get_column_letter(len(headers) + 1)}{ws_.max_row}"
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue(), f"חולצו {len(rows)} שורות מ-{pages_used} עמודים (עמודות: {', '.join(headers)})"
