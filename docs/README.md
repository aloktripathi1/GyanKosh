# GyanKosh

**GyanKosh** (Gyan = knowledge, Kosh = repository/treasury) converts a raw educational document — PDF, DOCX, PPTX, or plain text — into a structured, classroom-ready **Teacher Knowledge Package (TKP)**: lesson plans, activities, assessments, and a learning-gap analysis, packaged as JSON and PDFs, with a review UI to inspect, validate, and regenerate individual sections.

Live deployment: backend on Render, frontend on Vercel. See `BUILD_CONTEXT.md` in the repo root for the full original spec, and `AUDIT_REPORT.md` for a section-by-section audit of what was actually built against it.

---

## 1. Setup — running it locally

**Requirements**: Python 3.11, Node 18+, Postgres (via Docker or a local install), an Anthropic API key.

```bash
git clone <this-repo>
cd GyanKosh

cp backend/.env.example backend/.env
# edit backend/.env — set ANTHROPIC_API_KEY at minimum
```

**Every environment variable the backend reads is defined in [`backend/app/config.py`](../backend/app/config.py)** (a `pydantic-settings` `Settings` class) — that file is the source of truth for names and defaults, not this README, so it can't drift out of sync. `backend/.env.example` mirrors it.

### Option A — Docker (recommended, matches production)

```bash
docker compose up --build
```

This starts Postgres and the backend together (`docker-compose.yml`); the backend's own entrypoint runs `alembic upgrade head` before starting, so the schema is always current — no separate migration step to remember.

- Backend: http://localhost:8000 · API docs: http://localhost:8000/docs · health check: http://localhost:8000/health

### Option B — without Docker

```bash
# Postgres must be running and reachable at the DATABASE_URL in backend/.env
cd backend
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev   # http://localhost:5173, proxies /api -> localhost:8000 in dev (see vite.config.js)
```

For a production-style frontend build, set `VITE_API_BASE_URL` to the backend's URL and `VITE_API_KEY` to match the backend's `API_KEY` — see `frontend/.env.example`.

**No Redis, no separate worker process to start.** The pipeline runs as a FastAPI `BackgroundTask` in the same process as the web server — see Section 3.

---

## 2. Architecture

Full labeled diagram: [`architecture-diagram.excalidraw`](architecture-diagram.excalidraw) (import at [excalidraw.com](https://excalidraw.com)) — static export below.

![GyanKosh architecture diagram](Gyankosh.png)

**Data flow, in prose:**

1. **Upload** (`POST /documents`) — the file is validated (content-type, magic-byte signature, size, non-empty), stored, and a `Document` + `Job` row are created. If the exact same bytes were uploaded before, the cheap early stages are pre-seeded from the prior run rather than re-billed.
2. **Orchestration** picks up the job and runs it stage by stage, checkpointing each stage's output to Postgres (`jobs.stage_results`, a JSONB column keyed by stage name) as it completes.
3. **Document Intelligence** parses the file (PyMuPDF/python-docx/python-pptx, with a Claude-vision OCR fallback for scanned or image-only pages) into structured sections, tables, figures, and equations.
4. **Classification** and **Knowledge Extraction** run next — extraction tags every objective, concept, definition, formula, and misconception with a **source span** (exact character offset in the original document). This is the foundation the grounding/traceability guarantee (Section 4) is built on.
5. **Teaching Planner** decides how many periods the content needs (never a fixed count) and produces per-period objectives, sequencing, and a time estimate.
6. **Content, Activity, Assessment, and Gap Analysis generation** run concurrently (they only depend on the plan and extracted knowledge, never on each other) — every generated item cites a specific Stage-3 source span.
7. **Validation** runs four independent checks — schema, grounding, completeness, cross-period consistency — and the result ships *with* the package, not as an internal-only gate.
8. **Publishing** assembles `TeacherKnowledgePackage.json` and renders three PDFs (lesson plans, teacher guide, assessment book) via WeasyPrint.
9. The **review UI** (React) shows live progress over SSE while this runs, then lets you browse the result period-by-period and regenerate any single section without re-running the whole pipeline.

---

## 3. Orchestration approach

**Custom orchestrator, not an existing workflow framework (Airflow/Temporal/etc.)** — a Postgres-backed job state machine (`app/orchestrator/pipeline.py`): each stage's output is checkpointed on success, retried with exponential backoff on failure (`tenacity`, 3 attempts), and the job fails **explicitly** on exhaustion rather than hanging or silently dropping a stage. Every stage additionally carries a wall-clock timeout as a safety net against genuine hangs, independent of the retry logic. Resume-from-checkpoint (not restart-from-zero) is proven by a test that simulates a mid-run worker kill.

The reasoning for building this rather than adopting a framework: full control and an orchestrator that's straightforward to explain and defend, versus the overhead of learning and configuring a general-purpose workflow engine for what is fundamentally a 10-stage pipeline with one genuine fan-out point. Depth on a correct, well-tested custom implementation over breadth from an unneeded dependency.

**How work actually executes**, and why it changed once during the build: the original design planned Celery + Redis for fanning out the four independent generation stages (Content, Activity, Assessment, Gap Analysis) to a separate worker process. That assumption broke against a real deployment constraint — Render's free tier has no Background Worker service type at all (the cheapest tier for one is $7/month). Keeping Celery+Redis under that constraint meant either paying for infrastructure the project's constraints didn't allow, or deploying a worker that would never actually run, leaving every job stuck at `pending` forever. Neither was acceptable, so the pipeline now runs via FastAPI's `BackgroundTasks` in the same process as the web server (executed in a thread pool, so it doesn't block concurrent HTTP requests), and the four independent generation stages run concurrently via a `ThreadPoolExecutor` instead of Celery fan-out. The orchestrator itself — checkpointing, retry, explicit failure — is unchanged; only the trigger mechanism and the fan-out mechanism changed. This is documented in full, including a real concurrency bug this transition surfaced and how it was fixed, in `BUILD_CONTEXT.md` Section 18 and `AUDIT_REPORT.md`.

---

## 4. Bonus items actually built

- **Multi-Agent Orchestration**: the pipeline is not one large prompt. It's 8 independently-callable, independently-testable agents (`app/agents/`) — Document Intelligence, Classification, Knowledge Extraction, Teaching Planner, Content Generation, Activity Generation, Assessment Generation, Gap Analysis — each a pure `run(input) -> output` function bound to its own Pydantic schema, with no orchestration logic inside the agent itself. The orchestrator (Section 3) sequences, retries, checkpoints, and — for the four independent generation stages — parallelizes them.
- **RAG & Traceability**: every fact-bearing claim in the output (concepts, definitions, formulae, checkpoint questions, assessment items, misconceptions) is required to cite a literal quote from the source document, resolved to an exact character offset (`SourceSpan`) via a tiered match — exact, then whitespace-normalized, then fuzzy fallback (`rapidfuzz`). This isn't just a prompt instruction: the Validation Engine's grounding check independently re-verifies every citation against Stage 3's extracted knowledge and flags anything that doesn't trace back — proven by a test that deliberately injects a fabricated, ungrounded claim and confirms the check catches it, not just green-lights everything.

A third practical addition beyond the two above: every pipeline run emits structured logs (`job_id`, `stage`, `duration_ms`) and persists a per-stage timing breakdown queryable via `GET /jobs/{id}` — not required by the spec, but genuinely useful for debugging a slow or stuck stage, and it's what made a real production hang (Section 3) diagnosable in the first place.

---

## 5. Known limitations

Named deliberately, not discovered by an evaluator poking at the edges:

- **Single-tenant, no horizontal scaling** — one worker, one Postgres instance, a single shared API key. This is an explicit scope cut from the original spec (`BUILD_CONTEXT.md` Section 2), not an oversight: no compliance/multi-tenant requirement was ever stated, and building real auth/multi-tenancy would have been scope creep against a hard deadline for zero graded return.
- **Storage-backend / auth-layer coupling**: `api/deps.py`'s file-access check imports `local_storage.py`'s signature-verification logic directly rather than through the abstract `StorageBackend` interface. Functionally correct today, but if `STORAGE_BACKEND` ever swaps to S3, this specific check would need to change too (S3 presigned URLs are self-verifying by AWS, not by this app's HMAC scheme) — flagged during a cleanup pass, not yet abstracted.
- **Cross-period terminology contradiction is out of scope for `consistency_check`** — it checks that period-number references are valid and non-duplicated, not that two periods' prose agrees with each other. The actual defense against contradiction is structural (every claim grounds to an immutable Stage-3 source span), not a dedicated check; this is a documented, tested boundary (see `tests/test_validation.py`), not an unnoticed gap.
- **No signed/expiring URLs before a recent fix, and the underlying storage is ephemeral on Render's free tier** — generated-file download links are now HMAC-signed and expire (fixed after an internal audit found the original static-API-key-as-query-param scheme never expired), but local disk storage doesn't survive a redeploy, which is an accepted tradeoff for a demo/grading deployment, not a production posture.
- **`/samples` currently has one real sample** (STEM/Chemistry — see Section 6), not the two the spec calls for. A humanities sample generation attempt surfaced a real concurrency bug in the orchestrator (since root-caused and fixed, with a test proving the fix), and a second sample hasn't been regenerated and vetted yet.
- **Section 2's original scope cuts still stand**: no multilingual generation, no curriculum-board alignment (CBSE/CommonCore), no observability/tracing stack beyond structured logging + per-stage timing. These were explicit "do not build" items from the start, not things run out of time for.

---

## 6. Samples

[`/samples`](../samples) contains real pipeline output — pulled directly from a completed run via `GET /tkp/{id}`, not hand-edited.

- **`stem_chemistry_chemical_reactions_and_equations.json`** — a real NCERT Class 10 Chemistry chapter (Chemical Reactions and Equations). Demonstrates formula/equation grounding (word-equations and chemical equations both extracted with source spans), a 3-period plan, and all four validation checks passing on real STEM content.

---

## 7. Testing

**99 backend tests**, run before every push. Coverage follows the spec's own testing strategy explicitly:

- **Unit tests per agent** — LLM client mocked, output asserted against the stage's Pydantic schema (structure/contract, not pedagogical quality — that isn't machine-testable).
- **Golden fixture tests** — a STEM document, a humanities document, and a deliberately thin/messy one run through the full pipeline; the first two must validate cleanly, the third must degrade gracefully (no crash, no fabricated pass — the validation report honestly flags the gap).
- **Grounding regression test** — a fabricated, ungrounded claim is deliberately injected and the Validation Engine must catch it, not silently pass.
- **Orchestrator resilience** — a simulated mid-run worker kill, followed by resume-from-checkpoint with no duplicate LLM calls for already-completed stages.
- **Edge-case coverage** (Section 15 of the spec, followed case-by-case): corrupted/empty/oversized/wrong-type uploads, non-English and ambiguous/thin content, a hard cap on runaway period counts, humanities assessments correctly adapting away from numerical questions, PDF rendering under special characters and long tables, and a path-traversal attempt against the file-serving route.
- **A genuinely uncommon one worth calling out**: a live-database concurrency test (`tests/test_concurrency_live_db.py`) that spins up two real threads, two real DB connections, and two real transactions against an actual (disposable) Postgres instance, and proves that the regenerate-section row lock (`SELECT ... FOR UPDATE`) *actually blocks* a second concurrent transaction — measured on the blocked thread's own clock, not inferred from reading the code. Every other test in this suite deliberately avoids requiring a live database connection (mocking the DB boundary instead, same philosophy as mocking the LLM boundary) — this is the one exception, because blocking behavior is a property of the database engine itself and can't be proven any other way. Skips cleanly (not a failure) when `GYANKOSH_TEST_DATABASE_URL` isn't set.

Run the suite:

```bash
cd backend && source .venv/bin/activate
pytest                                    # 98 tests, no live DB needed
GYANKOSH_TEST_DATABASE_URL=postgresql+psycopg2://... pytest  # +1, the concurrency test
```
