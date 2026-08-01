# GyanKosh

Pipeline that converts a raw educational document into a structured, classroom-ready Teacher Knowledge Package (TKP). See [`BUILD_CONTEXT.md`](../BUILD_CONTEXT.md) for the full spec.

## Design highlights (bonus criteria this architecture already satisfies)

- **Multi-Agent Orchestration**: the pipeline isn't one large prompt — it's 8 independently-callable, independently-testable agents (Document Intelligence, Classification, Knowledge Extraction, Teaching Planner, Content/Activity/Assessment Generation, Gap Analysis), each a pure `run(input) -> output` function with its own Pydantic schema. A custom Postgres-backed orchestrator (`app/orchestrator/pipeline.py`) sequences them with per-stage retry/backoff, explicit failure (never silent), and checkpoint/resume — proven by a test that simulates a mid-run worker kill and confirms the job resumes from the last completed stage rather than restarting. The four independent generation stages (Content/Activity/Assessment/Gap Analysis) additionally run concurrently via a thread pool once their shared dependencies are ready, since they don't depend on each other — roughly a 2-3x speedup on that portion of the pipeline for free.
- **Grounding / Traceability (RAG-style, source-verified)**: every fact-bearing claim in the output — concepts, definitions, formulae, checkpoint questions, assessment items, misconceptions — is required to cite a literal quote from the original document, resolved to an exact character offset (`SourceSpan`) via a tiered match (exact → whitespace-normalized → fuzzy fallback). This isn't just requested in the prompt: the Validation Engine independently re-verifies every citation against Stage 3's extracted knowledge and flags anything that doesn't trace back — proven by a test that deliberately injects a fabricated, ungrounded claim and confirms the check catches it.
- **Observability**: every pipeline run emits structured logs (`job_id`, `stage`, `duration_ms`) for every stage attempt, retry, success, and failure, and persists a per-stage timing breakdown (`stage_timings` on the job) queryable via `GET /jobs/{id}` — not just a progress percentage, an actual trace of where time and retries went.

## Status

- **Milestone 1 (scaffold)**: repo structure, Pydantic schemas for all 10 stage outputs, Postgres schema + Alembic migration, FastAPI skeleton with the documented routes.
- **Milestone 2 (understanding pipeline)**: Document Intelligence agent (PDF/DOCX/PPTX/text parsing), Classification agent, and Knowledge Extraction agent — verified end-to-end on both a STEM and a humanities document, with source-span grounding resolved deterministically from LLM-cited quotes.
- **Milestone 3 (generation pipeline)**: Teaching Planner, Content, Activity, Assessment, and Gap Analysis agents — every generated item cites a Stage 3 extracted-knowledge item verbatim, resolved to that item's source span.
- **Milestone 4 (validation, publishing, orchestration)**: schema/grounding/completeness/consistency checks (with a passing test that deliberately injects an ungrounded claim), TKP.json assembly, WeasyPrint PDF rendering (lesson plans, teacher guide, assessment book), and a real orchestrator: retry-with-backoff, explicit failure, and checkpoint/resume — tested against a simulated mid-run worker kill.
- **Milestone 5 (review UI)**: Upload → JobProgress (SSE) → TKPReview (period-by-period, per-section regenerate, validation report surfaced, PDF downloads) — verified with a headless-Chromium walkthrough against real pipeline output, light and dark mode.

- **Deployed**: live on Render (Free tier) — verified end-to-end against a real NCERT chapter, not just synthetic test docs. Runs the pipeline as a FastAPI `BackgroundTask` in the same web service rather than a separate Celery worker + Redis, since Render's Background Worker service type has no free tier — the orchestrator itself (checkpoint/resume, retry, explicit failure) is unchanged, only how a job gets kicked off.
- **Milestone 6 (audit, hardening, cleanup)**: full pass against `BUILD_CONTEXT.md` (see `AUDIT_REPORT.md`), followed by closing the gaps it found — Section 15's edge-case checklist now has real test coverage (corrupted/empty/oversized/wrong-type uploads, non-English and thin/ambiguous content, humanities-adaptive assessments, concurrent-regenerate races, PDF rendering under special characters), a hard cap on teaching-plan period count, and a golden-fixture test proving STEM and humanities documents both validate cleanly while a deliberately thin document degrades gracefully instead of crashing or fabricating a pass. 78 backend tests, all passing.

**Known gaps**: `local_storage.py`'s file-serving path isn't traversal-hardened yet, and generated-PDF URLs reuse the static API key rather than a signed/expiring one (both called out in `AUDIT_REPORT.md`); cross-period terminology contradiction is a documented, argued-not-enforced scope boundary (grounding-by-reference is the actual defense against it); `/samples` still needs 2 real TKP.json files populated for submission.

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
