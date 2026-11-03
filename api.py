"""Optional REST API for EC2 deployments. Streamlit can run independently."""
from fastapi import FastAPI, HTTPException
from storage import Storage

app = FastAPI(title="Cloud FileOps API", version="1.0.0")
storage = Storage()

@app.get("/health")
def health():
    return {"status": "ok", "storage": "aws" if storage.aws_enabled else "local"}

@app.get("/files")
def files():
    return storage.list_records()

@app.get("/files/{file_id}")
def file_status(file_id: str):
    for record in storage.list_records():
        if record.get("file_id") == file_id:
            return record
    raise HTTPException(status_code=404, detail="File not found")
