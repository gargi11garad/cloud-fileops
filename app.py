import os
from datetime import datetime, timezone

import pandas as pd
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
mode = "AWS" if storage.aws_enabled else "Local demo"
st.caption(f"Storage: **{mode}** · AWS mode is enabled when AWS_REGION, S3_BUCKET, and DYNAMODB_TABLE are configured.")

records = storage.list_records()
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
            file_id = storage.new_id()
            item = {"file_id": file_id, "filename": upload.name, "status": "processing", "uploaded_at": datetime.now(timezone.utc).isoformat(), "content_type": upload.type or "application/octet-stream"}
            storage.save_upload(file_id, upload.name, upload.getvalue(), item["content_type"])
            storage.put_record(item)
            try:
                result = processor.process(upload.name, upload.getvalue())
                storage.save_result(file_id, result)
                item.update(status="completed", result=result, completed_at=datetime.now(timezone.utc).isoformat())
            except Exception as exc:
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
1. Create a private S3 bucket and a DynamoDB table with partition key `file_id` (String).
2. Set `AWS_REGION`, `S3_BUCKET`, and `DYNAMODB_TABLE` in Streamlit secrets or the EC2 environment.
3. Attach an EC2 instance role with least-privilege access to that bucket and table. Avoid storing access keys in source code.
4. Deploy the UI to Streamlit Community Cloud; run the API worker on EC2 using `uvicorn api:app --host 0.0.0.0 --port 8000`.

The app uses local storage automatically when AWS settings are absent, so you can try the workflow before provisioning cloud resources. See `README.md` for exact IAM and deployment steps.
""")

