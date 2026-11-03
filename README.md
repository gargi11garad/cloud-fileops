# Cloud FileOps

Streamlit dashboard and authenticated FastAPI backend for file uploads, processing, S3 storage, and DynamoDB status tracking. The hosted UI runs in local demo mode until the AWS backend is provisioned and its API settings are added to Streamlit secrets.

## Run locally

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

Local uploads, results, and metadata are stored in `.local_data/`.

## Deploy AWS backend

The CloudFormation template at `cloudformation.yaml` creates:

- A private S3 bucket with public access blocked, server-side encryption, and versioning.
- A DynamoDB table in on-demand mode, keyed by `file_id`.
- An EC2 instance with an IAM instance role scoped to that bucket, table, and generated API secret.
- A FastAPI backend behind Caddy HTTPS. The API's port 8000 is private; the security group exposes only ports 80 and 443. The instance does not expose SSH.

In AWS CloudFormation, create a stack from that template. Select a VPC and a **public subnet** with an Internet Gateway route. Keep the default `t4g.micro` instance for a low-traffic starter. Wait until the stack reaches `CREATE_COMPLETE`.

From the stack Outputs, copy `ApiBaseUrl`. Open Secrets Manager using the `ApiKeySecretArn` output and retrieve the generated `api_key`. In Streamlit Community Cloud, open **Manage app → Settings → Secrets** and add:

```toml
API_BASE_URL = "https://YOUR_EC2_IP.sslip.io"
API_KEY = "the-generated-secret-value"
```

The API key is sensitive. Keep it in Streamlit secrets and Secrets Manager; never commit it to GitHub. The EC2 API uses its instance role for AWS access, so no AWS access keys are required in Streamlit.

## Processing flow

The dashboard sends uploads to the API over HTTPS with an `X-API-Key` header. The API records a `processing` status, stores the original file under `uploads/{file_id}/...`, extracts metadata and supported CSV/JSON/text details, stores a JSON result under `results/{file_id}.json`, and updates DynamoDB to `completed` or `failed`. Uploads are limited to 20 MB. CSV results include row count, column names, null count, and up to five preview rows.

The API exposes public `GET /health` and authenticated `GET /files`, `GET /files/{file_id}`, and `POST /files` routes.

## Cost and cleanup

AWS charges depend on region and usage. An always-on EC2 instance, its public IPv4 address, EBS disk, network transfer, and stored file versions can incur charges; S3 and DynamoDB also bill for storage and requests. Review current regional rates and set an AWS Budget alert before launching. AWS's current VPC pricing lists public IPv4 at $0.005 per hour (about $3.65 for 730 hours), on top of EC2 and storage. [AWS VPC pricing](https://aws.amazon.com/vpc/pricing/)

The template retains the S3 bucket and DynamoDB table when the stack is deleted, to prevent accidental loss of uploaded data. Delete their contents and resources separately when you are certain they are no longer needed. Deleting the EC2 stack does not remove the retained files or table.
