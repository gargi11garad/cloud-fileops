# Cloud FileOps

A Streamlit file processing dashboard, Python REST API for EC2, S3 object storage, and DynamoDB status tracking. It runs in local demo mode without AWS credentials and switches to AWS when all three settings are present.

## Run locally

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

Open `http://localhost:8501`. Local uploads, results, and metadata live in `.local_data/`.

## AWS resources

Create an S3 bucket and a DynamoDB table named `file-processing-jobs` with partition key `file_id` (String). Configure environment variables (or Streamlit secrets):

```toml
AWS_REGION = "us-east-1"
S3_BUCKET = "your-unique-bucket-name"
DYNAMODB_TABLE = "file-processing-jobs"
```

For Streamlit Community Cloud, add these in **App settings → Secrets**. For EC2, export them in the service environment and attach an instance profile; do not put credentials in the repository.

The EC2 instance role needs `s3:PutObject` on `arn:aws:s3:::YOUR_BUCKET/*` and `dynamodb:PutItem`, `dynamodb:Scan` on the table ARN. Enable S3 default encryption and block public access. Create the table with on-demand billing.

## Deploy the dashboard to Streamlit Community Cloud

1. Push this repository to GitHub.
2. In Streamlit Community Cloud, choose **Create app**, select the repository, branch, and `app.py`.
3. Add AWS settings under app secrets if connecting to real AWS resources. Local demo mode needs no secrets.

## Run the REST API on EC2

Use Python 3.11+, install `requirements.txt`, configure an EC2 instance profile and environment, then run:

```bash
uvicorn api:app --host 0.0.0.0 --port 8000
```

The API exposes `GET /health`, `GET /files`, and `GET /files/{file_id}`. Restrict inbound access with the EC2 security group and place a TLS reverse proxy in front for public use.

## Processing workflow

The dashboard stores an initial `processing` record, writes the uploaded object to `uploads/{file_id}/...`, processes metadata and CSV/JSON/text previews, saves a JSON result under `results/{file_id}.json`, and updates DynamoDB to `completed` or `failed`. CSV results include row count, column names, null count, and up to five preview rows. Processing is synchronous in this starter; an SQS/Lambda or worker queue is a natural next step for large files or high throughput.
