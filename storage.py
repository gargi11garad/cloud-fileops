import json
import os
import uuid
from pathlib import Path


class Storage:
    def __init__(self):
        # Streamlit Community Cloud injects secrets through st.secrets; EC2 uses
        # environment variables. Environment variables take precedence.
        try:
            import streamlit as st
            secrets = st.secrets
        except Exception:
            secrets = {}
        self.region = os.getenv("AWS_REGION") or secrets.get("AWS_REGION")
        self.bucket = os.getenv("S3_BUCKET") or secrets.get("S3_BUCKET")
        self.table_name = os.getenv("DYNAMODB_TABLE") or secrets.get("DYNAMODB_TABLE")
        self.aws_enabled = bool(self.region and self.bucket and self.table_name)
        self.local_root = Path(os.getenv("LOCAL_DATA_DIR", ".local_data"))
        self.local_root.mkdir(parents=True, exist_ok=True)
        self.records_path = self.local_root / "records.json"
        self.s3 = self.table = None
        if self.aws_enabled:
            import boto3
            session = boto3.Session(region_name=self.region)
            self.s3 = session.client("s3")
            self.table = session.resource("dynamodb").Table(self.table_name)

    @staticmethod
    def new_id():
        return str(uuid.uuid4())

    def save_upload(self, file_id, filename, data, content_type):
        key = f"uploads/{file_id}/{Path(filename).name}"
        if self.aws_enabled:
            self.s3.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=content_type)
        else:
            path = self.local_root / key
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)

    def save_result(self, file_id, result):
        key = f"results/{file_id}.json"
        payload = json.dumps(result, default=str).encode()
        if self.aws_enabled:
            self.s3.put_object(Bucket=self.bucket, Key=key, Body=payload, ContentType="application/json")
        else:
            path = self.local_root / key
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)

    def put_record(self, record):
        if self.aws_enabled:
            self.table.put_item(Item=record)
        else:
            records = self._local_records()
            records = [r for r in records if r.get("file_id") != record["file_id"]]
            records.insert(0, record)
            self.records_path.write_text(json.dumps(records, indent=2, default=str), encoding="utf-8")

    def list_records(self):
        if self.aws_enabled:
            result = self.table.scan()
            return sorted(result.get("Items", []), key=lambda x: x.get("uploaded_at", ""), reverse=True)
        return sorted(self._local_records(), key=lambda x: x.get("uploaded_at", ""), reverse=True)

    def _local_records(self):
        if not self.records_path.exists():
            return []
        try:
            return json.loads(self.records_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []
