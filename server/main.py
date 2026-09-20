import base64
import json
import os
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import Response, JSONResponse
from fastapi.staticfiles import StaticFiles
from . import pdf_ops, wanted

app = FastAPI()


@app.post("/api/plan")
async def plan(text: str = Form(...)):
    ops = pdf_ops.parse(text)
    return {"ops": ops, "descriptions": [pdf_ops.describe(o) for o in ops]}


@app.post("/api/process")
async def process(file: UploadFile = File(...), ops: str = Form(...)):
    data = await file.read()
    try:
        parsed = json.loads(ops)
        parsed = [o for o in parsed if o.get("type") != "unknown"]
        out, log, kind = pdf_ops.apply(data, parsed)
    except Exception as e:  # noqa
        return JSONResponse({"error": str(e)}, status_code=400)
    media = "application/pdf" if kind == "pdf" else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return Response(out, media_type=media, headers={
        "X-Log": base64.b64encode(json.dumps(log, ensure_ascii=False).encode()).decode(),
        "X-Kind": kind,
    })


@app.get("/api/wanted")
async def wanted_info():
    return {"count": len(wanted.load_wanted())}


@app.post("/api/wanted")
async def wanted_upload(file: UploadFile = File(...)):
    try:
        n = wanted.save_wanted(await file.read())
    except Exception as e:  # noqa
        return JSONResponse({"error": f"קובץ לא תקין: {e}"}, status_code=400)
    return {"count": n}


dist = os.path.join(os.path.dirname(__file__), "..", "dist")
if os.path.isdir(dist):
    app.mount("/", StaticFiles(directory=dist, html=True), name="static")
