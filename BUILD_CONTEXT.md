# GyanKosh — Build Context

Project name: **GyanKosh** (Gyan = knowledge, Kosh = repository/treasury — names the deliverable itself, a Teacher Knowledge Package). Repo, package names, and deploy service names below use this.

Deadline: Aug 4, 2026. Today: Jul 31, 2026. No slack — build the core pipeline first, bonuses only if time remains.

## 1. Objective
Pipeline that converts a raw educational document (PDF/DOCX/PPT/text) into a structured, classroom-ready Teacher Knowledge Package (TKP): lesson plans, activities, assessments, learning-gap analysis, packaged as JSON + PDFs, with a review UI.

## 2. Explicit Scope Cuts (do not build these)
- No multilingual generation, no curriculum-board alignment (CBSE/CommonCore), no observability/tracing stack, no multi-tenant auth, no horizontal scaling. Single worker, single Postgres instance is correct for this prototype.
- Do not attempt these before the core 10-stage pipeline is fully working end to end.

## 3. Functional Requirements (10 stages)
1. Document Intelligence — parse PDF/DOCX/PPT/text, preserve structure (headings, tables, figures, equations).
2. Educational Classification — subject, grade, difficulty, topic, chapter, category, language.
3. Knowledge Extraction — objectives, prerequisites, concepts, definitions, formulae, keywords, examples, applications, misconceptions. **Every extracted item must be tagged with its source span in the original document** — this is required for grounding checks in stage 9, not optional.
4. Teaching Planner — split content into N periods (LLM decides N based on depth, not fixed at 5), each with objectives and sequencing rationale.
5. Classroom Content Generation (per period) — entry ticket, teacher script, blackboard notes, activities, checkpoint questions, exit ticket, homework, mentor moment.
6. Activity Generation (per period) — type, duration, materials, instructions, success criteria.
7. Assessment Generation — MCQ, short/long answer, numerical, with answer keys and rubrics.
8. Learning Gap Analysis — misconceptions, diagnostic questions, severity, remediation.
9. Validation — schema adherence (Pydantic), grounding check (claims must trace to Stage 3 source spans), completeness, cross-period consistency.
10. Publishing — assemble `TeacherKnowledgePackage.json`, render PDFs (lesson plans, teacher guide, assessment book), expose via review UI.
Plus: streaming progress API for the frontend during the run.

## 4. Non-Functional Requirements (only these matter, with why)
- **Pipeline reliability**: 10 chained stages. Checkpoint stage output after each stage completes; resumable from last checkpoint, not full restart. On stage failure: retry 2-3x with backoff, then fail explicitly (never silently drop a stage).
- **Progress visibility**: jobs run minutes. SSE stream, not blank-screen polling-only UX.
- **Cost control**: route cheap tasks (classification, extraction-to-schema) to a cheap/fast model; route reasoning-heavy tasks (planning, content generation, assessment generation) to a stronger model. Cache classification + extraction by document hash so re-runs don't re-bill.
- **Groundedness**: every generated claim must be traceable to Stage 3 extracted knowledge. This matters more than any other quality dimension — ungrounded content is a worse failure than a slow pipeline.
- **Modularity**: every stage is an independently callable, independently testable unit. No stage's logic lives inline in the orchestrator or the API layer.
- **Security**: light. Validate upload type/size, no public bucket exposure, signed/expiring URLs for generated PDFs, single API key auth. No compliance regime assumed — state this limitation in the README rather than over-building.

## 5. Core Entities (Postgres, JSONB for nested LLM output)
```
documents        id, filename, file_type, storage_path, uploaded_at
jobs             id, document_id, status, current_stage, progress_pct,
                 error, stage_results (JSONB, keyed by stage name), created_at, updated_at
tkp_versions      id, job_id, version, classification (JSONB), extracted_knowledge (JSONB),
                 teaching_plan (JSONB), period_content (JSONB), assessments (JSONB),
                 learning_gaps (JSONB), validation_report (JSONB), published_at
```
Every JSONB payload is validated against a Pydantic schema before it's written — the schema is the source of truth, the DB column is just storage.

## 6. Architecture — Components

```
Frontend (React/Vite, minimal)
   │  upload / poll or SSE / review TKP / regenerate one section
   ▼
API Layer (FastAPI)
   │  POST /documents · GET /jobs/{id} · GET /jobs/{id}/stream (SSE)
   │  GET /tkp/{id} · POST /tkp/{id}/regenerate/{section}
   ▼
Upload Service → validates file, stores raw doc, creates Document + Job
   ▼
Orchestrator (custom, DB-backed job state + Celery for fan-out)
   │  sequences stages, checkpoints stage_results, retries, emits progress
   ▼
Document Intelligence → Classification Agent → Knowledge Extraction Agent
   → Teaching Planner Agent
   → [parallel, fanned out via Celery] Content Agent | Activity Agent
     | Assessment Agent | Gap Analysis Agent
   → Validation Engine (schema + grounding + consistency)
   → Publishing Service (TKP.json + WeasyPrint PDFs)
   → Storage (Postgres + object storage, local disk for prototype /
     pluggable to S3)
```
Full labeled diagram: `docs/architecture-diagram.excalidraw` (already generated, import at excalidraw.com).

## 7. Key Decisions (condensed, with why)
| Area | Decision | Why |
|---|---|---|
| Orchestration | Custom orchestrator (Postgres job state) + Celery/Redis for fan-out execution | Full control, easiest to explain/defend in README under time pressure; avoids learning a new framework mid-deadline |
| Sync/async | Async job pattern, 202 + poll/stream | Pipeline runs minutes; forced by the streaming requirement itself |
| Progress | SSE | One-directional push, trivial in FastAPI, no extra infra vs WebSocket |
| Data layer | Postgres + JSONB | Transactional job state + schema-flexible nested LLM output, one DB not two |
| LLM routing | Cheap model for classification/extraction-to-schema, stronger model for planning/content/assessment generation | Direct cost-control answer, task-complexity-based not blanket |
| Structured output | Tool-use/schema mode on every LLM call, never "return JSON" in prose prompt | Makes schema validation meaningful, not a formality |
| Validation | Grounding-by-reference against Stage 3 source spans + schema + cross-period consistency check | Defensible, cheap, avoids unreliable "LLM judges LLM" hallucination checks |
| API style | REST | No complex client-driven nested queries needed; GraphQL buys nothing here |
| Auth | Single API key | No compliance/multi-tenant requirement stated; full RBAC is over-engineering here |
| Deployment | Render (backend + worker + Postgres + Redis), frontend on Vercel | Long-lived worker + real Postgres needed; serverless timeout limits rule out pure Vercel backend |
| PDF | HTML/CSS templates → WeasyPrint | Fast to style/iterate vs a raw PDF library |
| Storage | Interface-abstracted, local disk default, S3-swappable | Avoids extra infra setup now, production-shaped later |

## 8. Tech Stack

| Layer | Choice | Alternatives considered | Why |
|---|---|---|---|
| Backend language/framework | Python + FastAPI | Node/Express, Django | Strongest LLM/AI tooling (Anthropic SDK, Pydantic, PyMuPDF/python-docx for parsing). Django's batteries (admin, ORM conventions) are dead weight — no admin panel, no complex relational app. FastAPI is native async (needed for SSE) and integrates directly with Pydantic, which is the validation backbone for every LLM output |
| ORM/migrations | SQLAlchemy + Alembic | Raw SQL, Tortoise ORM, Prisma | De facto standard with FastAPI, mature async support, Alembic gives migration history — matters since JSONB schema shifts as prompts get tuned mid-build |
| LLM provider | Anthropic API, tiered: Haiku-tier for classification/extraction, Sonnet-tier for planning/content/assessment/gap generation | OpenAI, self-hosted open-source | Already on Claude; structured/tool-use output fits schema-bound generation. Self-hosting is a non-starter under a 4-day deadline (infra + tuning time). No reason to add a second vendor for no gain |
| Frontend framework | React (Vite) | Next.js, Streamlit, plain HTML/JS | Streamlit fights async job polling/SSE (rejected in Phase 3). Next.js buys SSR/routing not needed for a single upload→progress→review flow. Plain HTML/JS is a valid faster alternative if not fluent in React — same backend contract either way; React chosen for component reuse across the review UI (period cards, regenerate buttons repeat a lot), not for SSE (`EventSource` is trivial in both) |
| PDF | WeasyPrint (HTML/CSS → PDF) | Raw PDF library | Fast to style/iterate |
| DB | Postgres (JSONB columns) | Mongo, pure relational | Transactional job state + schema-flexible nested LLM output, one DB not two |
| Task queue | Celery + Redis | In-process asyncio tasks | Decouples web process from long-running pipeline; reads as real orchestration under evaluation, not a hack |
| Deploy | Render (backend/worker/Postgres/Redis), Vercel (frontend) | Pure Vercel, Streamlit Cloud | Long-lived worker + real Postgres ruled out serverless-only |

If not fluent in React and time gets tighter than the component-reuse benefit is worth, swap to plain HTML/JS/htmx — same backend contract, zero framework overhead.

## 9. Folder Structure
```
gyankosh/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py                 # pydantic-settings, .env
│   │   ├── db.py
│   │   ├── api/
│   │   │   ├── documents.py
│   │   │   ├── jobs.py
│   │   │   └── tkp.py
│   │   ├── models/                   # SQLAlchemy: Document, Job, TKPVersion
│   │   ├── schemas/                  # Pydantic: one per stage output
│   │   ├── orchestrator/
│   │   │   ├── pipeline.py           # sequencing, checkpointing, resume
│   │   │   └── progress.py           # progress events -> jobs table -> SSE
│   │   ├── agents/                   # one module per LLM stage, pure functions
│   │   │   ├── document_intelligence.py
│   │   │   ├── classification.py
│   │   │   ├── knowledge_extraction.py
│   │   │   ├── teaching_planner.py
│   │   │   ├── content_generator.py
│   │   │   ├── activity_generator.py
│   │   │   ├── assessment_generator.py
│   │   │   └── gap_analysis.py
│   │   ├── validation/
│   │   │   ├── schema_check.py
│   │   │   ├── grounding_check.py
│   │   │   └── consistency_check.py
│   │   ├── publishing/
│   │   │   ├── json_builder.py
│   │   │   └── pdf_renderer.py
│   │   ├── storage/
│   │   │   ├── base.py               # interface
│   │   │   └── local_storage.py
│   │   ├── llm/
│   │   │   ├── client.py             # Anthropic wrapper, model routing by task
│   │   │   └── prompts/              # one template per agent
│   │   └── tasks/                    # Celery tasks wrapping orchestrator stages
│   ├── tests/
│   ├── alembic/
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   └── src/pages/ (Upload, JobProgress, TKPReview)
├── samples/                          # min 2 sample TKP.json for submission
├── docs/
│   ├── architecture-diagram.excalidraw
│   └── README.md
└── docker-compose.yml                # postgres + redis + backend + worker, local dev
```

## 10. Coding Conventions
- Every agent module: `run(input: <PydanticModel>) -> <PydanticModel>`. Pure function, no side effects beyond the LLM call. Testable in isolation, no orchestrator logic leaking in.
- Every stage call wrapped by the orchestrator: try/except → checkpoint on success, retry with backoff on failure (max 3), explicit `jobs.error` + failed status on exhaustion. Never fail silently or skip a stage.
- All LLM calls use structured output (tool-use schema mode) bound to the Pydantic schema for that stage. No prompt-and-hope-it's-JSON.
- Secrets/config via `.env` + pydantic-settings: `ANTHROPIC_API_KEY`, `DATABASE_URL`, `REDIS_URL`, `STORAGE_BACKEND`.
- Storage access always through the `storage/base.py` interface, never direct filesystem/S3 calls from agents or API routes.

## 11. Build Order
1. Scaffold: Pydantic schemas for all 10 stage outputs, DB schema, API skeleton, bare deploy live.
2. Understanding pipeline: Document Intelligence → Classification → Knowledge Extraction, tested on one STEM doc and one humanities doc.
3. Generation pipeline: Teaching Planner, then Content Agent fully working end to end, then clone the pattern for Activity/Assessment/Gap agents.
4. Validation + Publishing + Orchestration: schema/grounding/consistency checks, TKP.json + PDF render, retry/resume, SSE wired through.
5. Review UI: upload, progress bar, TKP viewer, single-section regenerate.
6. Harden: test across 3 subject types, fix edge cases, write README (setup, architecture diagram, orchestration explanation), 2 sample TKP.json in `/samples`, final deploy.

## 12. Git Workflow
Push to GitHub after every major change, not just at milestone ends: after each stage/agent is working and tested, after schema changes, after orchestrator changes, after each build-order milestone in Section 11. Small frequent commits with clear messages (`feat: knowledge extraction agent with source-span tagging`, `fix: retry backoff on schema validation failure`) over large infrequent ones — under a 4-day deadline, an uncommitted half-day of work lost to a crash is not recoverable time. Never leave a working state uncommitted at the end of a session.

## 13. Definition of Done (per stage)
- Stage output validates against its Pydantic schema on the first or retried call.
- Knowledge Extraction: every concept/definition/formula carries a source-span reference.
- Validation Engine: flags at least one deliberately-injected ungrounded claim in a test run (proves the grounding check actually works, not just green-lights everything).
- Pipeline survives a mid-run worker kill and resumes from the last checkpointed stage instead of restarting.
- End-to-end run succeeds on both a STEM doc (equations/formulae) and a humanities doc (subjective narrative) — this is the explicit rubric criterion, don't only test on one doc type.
