# FitCheck AI — Backend API

FastAPI service for virtual try-on uploads and generation jobs.

See [BACKEND_ARCHITECTURE.md](./BACKEND_ARCHITECTURE.md) for the full design.

## Setup

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt
cp .env.example .env
```

## Run

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```

- API docs: http://127.0.0.1:8001/docs
- Health: http://127.0.0.1:8001/api/v1/health

## Tests

```bash
pytest
```
