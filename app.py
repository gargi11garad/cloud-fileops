import os
from datetime import datetime, timezone

import pandas as pd
import requests
import streamlit as st

from processor import FileProcessor
from storage import Storage

st.set_page_config(page_title="Cloud FileOps", page_icon="☁️", layout="wide")

st.markdown("""
<style>
.stApp { background: #f5f7fb; }
[data-testid="stMetric"] { background: white; border: 1px solid #e7eaf1; padding: 16px; border-radius: 12px; }
.hero { padding: 24px 28px; background: linear-gradient(120deg,#10233f,#176b87); color: white; border-radius: 16px; margin-bottom: 20px; }
.hero p { color: #d7e6ef; margin-bottom: 0; }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="hero"><h1>☁️ Cloud FileOps</h1><p>Upload, process, and track files with a dependable AWS-ready workflow.</p></div>', unsafe_allow_html=True)

@st.cache_resource
def services():
    return Storage(), FileProcessor()

storage, processor = services()
api_base = os.getenv("API_BASE_URL")
api_key = os.getenv("API_KEY")
try:
    api_base = api_base or st.secrets.get("API_BASE_URL")
    api_key = api_key or st.secrets.get("API_KEY")
except Exception:
    pass
remote_mode = bool(api_base and api_key)
mode = "AWS backend via EC2 API" if remote_mode else ("AWS direct" if storage.aws_enabled else "Local demo")
mode_detail = "Connected to the protected backend." if remote_mode else ("This process has AWS environment configuration." if storage.aws_enabled else "Configure API_BASE_URL and API_KEY in Streamlit secrets to use EC2, S3, and DynamoDB.")
st.caption(f"Storage: **{mode}** · {mode_detail}")

def list_records():
    if not remote_mode:
        return storage.list_records()
    try:
        response = requests.get(f"{api_base.rstrip('/')}/files", headers={"X-API-Key": api_key}, timeout=15)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        st.error(f"Could not reach the EC2 processing API: {exc}")
        return []

records = list_records()
total = len(records)
done = sum(r.get("status") == "completed" for r in records)
failed = sum(r.get("status") == "failed" for r in records)
c1, c2, c3, c4 = st.columns(4)
c1.metric("Files processed", total)
c2.metric("Completed", done)
c3.metric("Failed", failed)
c4.metric("Success rate", f"{(done / total * 100):.0f}%" if total else "—")

upload_tab, history_tab, guide_tab = st.tabs(["Process files", "Processing history", "AWS setup"])
with upload_tab:
    st.subheader("Add files to the processing queue")
    uploads = st.file_uploader("Choose one or more files", accept_multiple_files=True, help="Demo mode supports text, CSV, JSON, and other files up to 20 MB each.")
    if uploads and st.button("Process files", type="primary"):
        progress = st.progress(0)
        for i, upload in enumerate(uploads):
            try:
                contents = upload.getvalue()
                if remote_mode:
                    response = requests.post(
                        f"{api_base.rstrip('/')}/files",
                        headers={"X-API-Key": api_key},
                        files={"file": (upload.name, contents, upload.type or "application/octet-stream")},
                        timeout=120,
                    )
                    response.raise_for_status()
                    item = response.json()
                    if item.get("status") == "failed":
                        st.error(f"{upload.name}: {item.get('error', 'Processing failed')}")
                else:
                    file_id = storage.new_id()
                    item = {"file_id": file_id, "filename": upload.name, "status": "processing", "uploaded_at": datetime.now(timezone.utc).isoformat(), "content_type": upload.type or "application/octet-stream"}
                    storage.save_upload(file_id, upload.name, contents, item["content_type"])
                    storage.put_record(item)
                    result = processor.process(upload.name, contents)
                    storage.save_result(file_id, result)
                    item.update(status="completed", result=result, completed_at=datetime.now(timezone.utc).isoformat())
                    storage.put_record(item)
            except Exception as exc:
                if remote_mode:
                    st.error(f"Could not process {upload.name}: {exc}")
                else:
                    item.update(status="failed", error=str(exc), completed_at=datetime.now(timezone.utc).isoformat())
                    storage.put_record(item)
            progress.progress((i + 1) / len(uploads))
        st.success(f"Processed {len(uploads)} file(s).")
        st.rerun()
    st.info("Processing extracts file metadata and, for CSV, a compact schema and preview. Original files and JSON results are stored separately.")

with history_tab:
    st.subheader("Recent processing activity")
    if records:
        df = pd.DataFrame([{ "File": r.get("filename"), "Status": r.get("status"), "Uploaded": r.get("uploaded_at"), "Type": r.get("content_type"), "ID": r.get("file_id")} for r in records])
        st.dataframe(df, use_container_width=True, hide_index=True)
        with st.expander("Inspect record details"):
            for r in records:
                with st.container(border=True):
                    st.write(f"**{r.get('filename')}** · {r.get('status')}")
                    st.json(r)
    else:
        st.write("No files yet. Upload a file to see its processing history here.")

with guide_tab:
    st.subheader("Connect AWS services")
    st.markdown("""
1. Deploy `infrastructure/cloudformation.yaml` in AWS CloudFormation using a public subnet.
2. Copy the stack's `ApiBaseUrl` output and retrieve `api_key` from the secret named by `ApiKeySecretArn`.
3. In Streamlit Community Cloud, open **Manage app → Settings → Secrets** and set `API_BASE_URL` and `API_KEY`.
4. The EC2 instance uses an IAM role for S3 and DynamoDB. AWS access keys do not belong in Streamlit or GitHub.

The app uses local storage until the API settings are configured. See `README.md` for the stack setup and cost notes.
""")

