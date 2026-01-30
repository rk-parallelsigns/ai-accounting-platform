# Backend (FastAPI)

## Run locally on macOS

```bash
cd ~/code/ai-accounting-platform/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

export SUPABASE_URL="https://your-project.supabase.co"
export SUPABASE_SERVICE_ROLE_KEY="your-service-role-key"

uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

## Required environment variables

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`

## Example curl commands

```bash
curl http://localhost:8000/health
```

```bash
curl -H "Authorization: Bearer <SUPABASE_JWT>" \
  http://localhost:8000/me
```

```bash
curl -H "Authorization: Bearer <SUPABASE_JWT>" \
  http://localhost:8000/clients
```

```bash
curl -H "Authorization: Bearer <SUPABASE_JWT>" \
  http://localhost:8000/datasets
```

```bash
curl -X POST http://localhost:8000/datasets/create \
  -H "Authorization: Bearer <SUPABASE_JWT>" \
  -H "Content-Type: application/json" \
  -d '{"client_id":"<uuid>","name":"January Close","notes":"optional"}'
```

```bash
curl -X POST http://localhost:8000/datasets/<dataset_id>/files \
  -H "Authorization: Bearer <SUPABASE_JWT>" \
  -H "Content-Type: application/json" \
  -d '{"filename":"ledger.csv","file_type":"csv","storage_path":"s3://bucket/ledger.csv","size_bytes":12345}'
```

```bash
curl -H "Authorization: Bearer <SUPABASE_JWT>" \
  http://localhost:8000/datasets/<dataset_id>
```

```bash
curl -X POST http://localhost:8000/datasets/<dataset_id>/process \
  -H "Authorization: Bearer <SUPABASE_JWT>"
```
