import hashlib
import io
import json
from datetime import datetime, timezone

import pandas as pd


class FileProcessor:
    """Small deterministic processor; safe to extend with domain-specific jobs."""

    def process(self, filename: str, data: bytes) -> dict:
        digest = hashlib.sha256(data).hexdigest()
        result = {"filename": filename, "size_bytes": len(data), "sha256": digest, "processed_at": datetime.now(timezone.utc).isoformat()}
        ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
        if ext == "csv":
            frame = pd.read_csv(io.BytesIO(data))
            result.update({"kind": "csv", "rows": int(len(frame)), "columns": [str(c) for c in frame.columns], "null_cells": int(frame.isna().sum().sum()), "preview": json.loads(frame.head(5).to_json(orient="records", date_format="iso"))})
        elif ext == "json":
            parsed = json.loads(data.decode("utf-8"))
            result.update({"kind": "json", "top_level_type": type(parsed).__name__})
        elif ext in ("txt", "md", "log"):
            content = data.decode("utf-8", errors="replace")
            result.update({"kind": "text", "characters": len(content), "lines": len(content.splitlines()), "preview": content[:500]})
        else:
            result.update({"kind": "binary", "extension": ext or "unknown"})
        return result
