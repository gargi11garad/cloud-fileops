"""Authenticated processing API intended to run on EC2 behind HTTPS."""
import hmac
import os
from datetime import datetime, timezone

from fastapi import FastAPI, File, Header, HTTPException, UploadFile

from processor import FileProcessor
from storage import Storage

app = FastAPI(title="Cloud FileOps API", version="1.0.0")
storage = Storage()
processor = FileProcessor()
MAX_UPLOAD_BYTES = 20 * 1024 * 1024

def authorize(x_api_key: str | None):
    expected = os.getenv("API_KEY", "")
    if not expected:
        raise HTTPException(status_code=503, detail="API key is not configured")
    if not x_api_key or not hmac.compare_digest(x_api_key, expected):
        raise HTTPException(status_code=401, detail="Invalid API key")

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/files")
def files(x_api_key: str | None = Header(default=None)):
    authorize(x_api_key)
    return storage.list_records()

@app.get("/files/{file_id}")
def file_status(file_id: str, x_api_key: str | None = Header(default=None)):
    authorize(x_api_key)
    for record in storage.list_records():
        if record.get("file_id") == file_id:
            return record
    raise HTTPException(status_code=404, detail="File not found")

@app.post("/files", status_code=201)
async def upload_file(file: UploadFile = File(...), x_api_key: str | None = Header(default=None)):
    authorize(x_api_key)
    filename = file.filename or "upload.bin"
    if len(filename) > 255:
        raise HTTPException(status_code=400, detail="Filename is too long")
    payload = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(payload) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Maximum upload size is 20 MB")

    file_id = storage.new_id()
    now = datetime.now(timezone.utc).isoformat()
    record = {"file_id": file_id, "filename": filename, "status": "processing", "uploaded_at": now, "content_type": file.content_type or "application/octet-stream"}
    storage.put_record(record)
    try:
        storage.save_upload(file_id, filename, payload, record["content_type"])
        result = processor.process(filename, payload)
        storage.save_result(file_id, result)
        record.update(status="completed", result=result, completed_at=datetime.now(timezone.utc).isoformat())
    except Exception as exc:
        record.update(status="failed", error=str(exc)[:1000], completed_at=datetime.now(timezone.utc).isoformat())
    storage.put_record(record)
    return record
