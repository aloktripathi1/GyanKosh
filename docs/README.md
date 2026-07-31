# GyanKosh

Pipeline that converts a raw educational document into a structured, classroom-ready Teacher Knowledge Package (TKP). See [`BUILD_CONTEXT.md`](../BUILD_CONTEXT.md) for the full spec.

## Status

- **Milestone 1 (scaffold)**: repo structure, Pydantic schemas for all 10 stage outputs, Postgres schema + Alembic migration, FastAPI skeleton with the documented routes.
- **Milestone 2 (understanding pipeline)**: Document Intelligence agent (PDF/DOCX/PPTX/text parsing), Classification agent, and Knowledge Extraction agent — verified end-to-end on both a STEM and a humanities document, with source-span grounding resolved deterministically from LLM-cited quotes.
- **Milestone 3 (generation pipeline)**: Teaching Planner, Content, Activity, Assessment, and Gap Analysis agents — every generated item cites a Stage 3 extracted-knowledge item verbatim, resolved to that item's source span.
- **Milestone 4 (validation, publishing, orchestration)**: schema/grounding/completeness/consistency checks (with a passing test that deliberately injects an ungrounded claim), TKP.json assembly, WeasyPrint PDF rendering (lesson plans, teacher guide, assessment book), and a real orchestrator: retry-with-backoff, explicit failure, and checkpoint/resume — tested against a simulated mid-run worker kill.
- **Milestone 5 (review UI)**: Upload → JobProgress (SSE) → TKPReview (period-by-period, per-section regenerate, validation report surfaced, PDF downloads) — verified with a headless-Chromium walkthrough against real pipeline output, light and dark mode.

**Known gaps** (Milestone 6 territory): no live Postgres/Redis/Docker access in the dev sandbox this was built in, so the orchestrator's DB integration is unit-tested against a fake session rather than end-to-end — needs a real smoke test via `docker compose up` or the Render deploy. Section 15's edge-case checklist (corrupted uploads, image-only PDFs, oversized docs, non-English content, period-count capping, etc.) isn't covered yet.

**Not yet deployed**: Render deploy is pending — `render.yaml` is committed but needs the repo connected via the Render dashboard (requires your account access).

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

![GyanKosh architecture diagram](Gyankosh.png)

See Section 6 of `BUILD_CONTEXT.md` and `architecture-diagram.excalidraw` in this folder for the editable source.
