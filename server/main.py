import base64
import json
import os
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import Response, JSONResponse
from fastapi.staticfiles import StaticFiles
from . import pdf_ops

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
        out, log = pdf_ops.apply(data, parsed)
    except Exception as e:  # noqa
        return JSONResponse({"error": str(e)}, status_code=400)
    return Response(out, media_type="application/pdf", headers={"X-Log": base64.b64encode(json.dumps(log, ensure_ascii=False).encode()).decode()})


dist = os.path.join(os.path.dirname(__file__), "..", "dist")
if os.path.isdir(dist):
    app.mount("/", StaticFiles(directory=dist, html=True), name="static")
