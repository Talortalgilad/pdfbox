"""רשימת המבוקשים של הוק והצלבה מולה."""
import io
import os
import re
import collections
from openpyxl import load_workbook, Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
WANTED_PATH = os.path.join(DATA_DIR, "wanted.xlsx")
CONDS = ["NE", "OH", "SV", "AR", "BE", "Q", "Q-SV", "Q-AR", "A-NE"]


def norm(s):
    return re.sub(r"[^A-Z0-9]", "", str(s).upper())


def load_wanted():
    """מחזיר {מקט מנורמל: מקט מקורי}. קורא כל עמודה שנראית כמו P/N מכל הלשוניות."""
    if not os.path.exists(WANTED_PATH):
        return {}
    wb = load_workbook(WANTED_PATH, data_only=True, read_only=True)
    out = {}
    for ws in wb:
        for r in ws.iter_rows(values_only=True):
            for v in r:
                if v is None:
                    continue
                t = str(v).strip()
                if 2 <= len(t) <= 40 and " " not in t and norm(t) not in ("PARTNUMBER", "PN", "PARTNO", "MPN"):
                    out.setdefault(norm(t), t)
    return out


def save_wanted(data: bytes):
    os.makedirs(DATA_DIR, exist_ok=True)
    load_workbook(io.BytesIO(data), read_only=True)  # ולידציה שזה אקסל תקין
    with open(WANTED_PATH, "wb") as f:
        f.write(data)
    return len(load_wanted())


def _pn_col(headers):
    for i, h in enumerate(headers):
        if re.search(r"^(P/?N|PART|PARTNUMBER|MPN|ITEM)", norm(h)):
            return i
    return 0


def _col(headers, *names):
    for i, h in enumerate(headers):
        if norm(h) in names:
            return i
    return None


def match_workbook(xlsx_bytes: bytes, source_name: str):
    """מקבל את האקסל שחולץ מהמניפסט ומחזיר אקסל עם הצלבה מול המבוקשים."""
    wanted = load_wanted()
    if not wanted:
        raise ValueError("לא נמצאה רשימת מבוקשים בשרת — העלה אותה בממשק")
    src = load_workbook(io.BytesIO(xlsx_bytes)).active
    rows = list(src.iter_rows(values_only=True))
    headers = [str(h or "") for h in rows[0]]
    ipn, idesc = _pn_col(headers), _col(headers, "KEYWORD", "DESCRIPTION", "DESC", "NOMENCLATURE")
    icond, iqty = _col(headers, "COND", "CONDITION", "CD"), _col(headers, "QTY", "QTYOH", "QUANTITY", "QUANTITYOH")
    isn = _col(headers, "SERIALNUMBER", "SN", "SERIAL", "SERIALBATCH")
    ipage = len(headers) - 1

    hits, agg = [], collections.OrderedDict()
    for r in rows[1:]:
        pn = r[ipn]
        if pn is None or norm(pn) not in wanted:
            continue
        pn = str(pn).strip()
        get = lambda i: ("" if i is None or r[i] is None else str(r[i]).strip())
        qty = get(iqty)
        qty = int(re.match(r"\d+", qty).group()) if re.match(r"\d+", qty) else 0
        cond, sn, desc = get(icond), get(isn), get(idesc)
        hits.append([pn, desc, cond, qty, sn, r[ipage]])
        a = agg.setdefault(pn, {"desc": desc, "lines": 0, "qty": 0, "c": collections.Counter(), "sn": []})
        a["lines"] += 1
        a["qty"] += qty
        a["c"][cond] += qty
        if sn and sn.upper() != "NSN":
            a["sn"].append(sn)

    out = Workbook()
    s = out.active
    s.title = "MATCH SUMMARY"
    s.append(["P/N", "DESCRIPTION", "LINES", "TOTAL QTY"] + CONDS + ["S/N LIST"])
    for pn, a in sorted(agg.items(), key=lambda x: -x[1]["qty"]):
        s.append([pn, a["desc"], a["lines"], a["qty"]] + [a["c"].get(c, 0) or None for c in CONDS] + [", ".join(a["sn"])])
    n = max(s.max_row, 2)
    s.append([])
    s.append(["TOTAL", None, f"=SUM(C2:C{n})", f"=SUM(D2:D{n})"] +
             [f"=SUM({get_column_letter(5 + i)}2:{get_column_letter(5 + i)}{n})" for i in range(len(CONDS))])
    d = out.create_sheet("MATCH LINES")
    d.append(["P/N", "DESCRIPTION", "COND", "QTY", "S/N", "PAGE"])
    for h in hits:
        d.append(h)
    full = out.create_sheet("FULL DATA")
    for r in rows:
        full.append(list(r))
    info = out.create_sheet("INFO")
    info["A1"], info["B1"] = "SOURCE", source_name
    info["A2"], info["B2"] = "WANTED LIST", f"{len(wanted)} P/Ns (server copy)"
    info["A3"], info["B3"] = "MATCH RULE", "Exact P/N match after stripping dashes/spaces/case"
    info["A4"], info["B4"] = "MATCHED P/N", f"=COUNTA('MATCH SUMMARY'!A2:A{n})"
    info["A5"], info["B5"] = "MATCHED LINES", f"=COUNTA('MATCH LINES'!A2:A{max(d.max_row, 2)})"

    fill = PatternFill("solid", fgColor="1F3A5F")
    for sh in (s, d, full):
        for c in sh[1]:
            c.fill, c.font, c.alignment = fill, Font(name="Arial", bold=True, color="FFFFFF"), Alignment(horizontal="center")
        for row in sh.iter_rows(min_row=2):
            for c in row:
                c.font = Font(name="Arial", size=10)
        sh.freeze_panes = "A2"
    for c in s[s.max_row]:
        c.font = Font(name="Arial", size=10, bold=True)
    for j, w in enumerate([18, 40, 7, 10] + [6] * len(CONDS) + [60], 1):
        s.column_dimensions[get_column_letter(j)].width = w
    for j, w in enumerate([18, 40, 7, 6, 24, 9], 1):
        d.column_dimensions[get_column_letter(j)].width = w
    info.column_dimensions["A"].width = 16
    info.column_dimensions["B"].width = 90
    for row in info.iter_rows():
        for c in row:
            c.font = Font(name="Arial", size=10)
    buf = io.BytesIO()
    out.save(buf)
    return buf.getvalue(), f"הצלבה: {len(agg)} מק\"טים מבוקשים נמצאו, {len(hits)} שורות, {sum(a['qty'] for a in agg.values())} יחידות"
