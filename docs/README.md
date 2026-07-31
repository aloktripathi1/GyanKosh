# GyanKosh

Pipeline that converts a raw educational document into a structured, classroom-ready Teacher Knowledge Package (TKP). See [`BUILD_CONTEXT.md`](../BUILD_CONTEXT.md) for the full spec.

## Status

Milestone 1 (scaffold) complete: repo structure, Pydantic schemas for all 10 stage outputs, Postgres schema + Alembic migration, FastAPI skeleton with the documented routes, empty backend deploy on Render. No agent/LLM logic yet — every `agents/`, `validation/`, `publishing/`, and `orchestrator.pipeline.run_stage` function raises `NotImplementedError` with a milestone marker.

## Local setup

```bash
cp backend/.env.example backend/.env   # fill in ANTHROPIC_API_KEY, API_KEY
docker compose up --build
```

Backend: http://localhost:8000/health · API docs: http://localhost:8000/docs

Or without Docker:

```bash
cd backend
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

## Architecture

See Section 6 of `BUILD_CONTEXT.md` and `architecture-diagram.excalidraw` in this folder.
