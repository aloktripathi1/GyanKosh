# GyanKosh — Build Context

Project name: **GyanKosh** (Gyan = knowledge, Kosh = repository/treasury — names the deliverable itself, a Teacher Knowledge Package). Repo, package names, and deploy service names below use this.

Deadline: Aug 4, 2026. Today: Jul 31, 2026. No slack — build the core pipeline first, bonuses only if time remains.

## 1. Objective
Pipeline that converts a raw educational document (PDF/DOCX/PPT/text) into a structured, classroom-ready Teacher Knowledge Package (TKP): lesson plans, activities, assessments, learning-gap analysis, packaged as JSON + PDFs, with a review UI.

## 2. Explicit Scope Cuts (do not build these)
- No multilingual generation, no curriculum-board alignment (CBSE/CommonCore), no observability/tracing stack, no multi-tenant auth, no horizontal scaling. Single worker, single Postgres instance is correct for this prototype.
- Do not attempt these before the core 10-stage pipeline is fully working end to end.
- These cuts stand even under a "production quality" bar — quality here means the core pipeline is robust, tested, and well-engineered, not that scope expands to include bonus features. Depth on the 10 stages over breadth across the bonus list.

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
│   │   └── tasks/                    # FastAPI BackgroundTasks wrapping orchestrator stages (see Section 18)
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
└── docker-compose.yml                # postgres + backend, local dev (see Section 18)
```

## 10. Coding Conventions
- Every agent module: `run(input: <PydanticModel>) -> <PydanticModel>`. Pure function, no side effects beyond the LLM call. Testable in isolation, no orchestrator logic leaking in.
- Every stage call wrapped by the orchestrator: try/except → checkpoint on success, retry with backoff on failure (max 3), explicit `jobs.error` + failed status on exhaustion. Never fail silently or skip a stage.
- All LLM calls use structured output (tool-use schema mode) bound to the Pydantic schema for that stage. No prompt-and-hope-it's-JSON.
- Secrets/config via `.env` + pydantic-settings: `ANTHROPIC_API_KEY`, `DATABASE_URL`, `STORAGE_BACKEND` (see Section 18 — no `REDIS_URL`, Celery/Redis were removed).
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
- Every relevant edge case in Section 15 has a passing test, not just the happy path.

## 14. Testing Strategy
- **Unit tests per agent**: mock the LLM client, feed known inputs, assert output validates against the stage's Pydantic schema. Tests structure and contract, not pedagogical quality (that's not machine-testable).
- **Fixture/golden tests**: 3 fixed input docs — one STEM, one humanities, one deliberately messy (poor structure, thin content) — run through the full pipeline in CI/dev. Assert no unhandled exceptions and a clean validation report on the first two; assert the third produces a graceful low-confidence flag, not a crash or fabricated content.
- **Grounding regression test**: inject a known ungrounded claim into a mocked content-agent response, assert the Validation Engine catches it. This is the test that proves Section 6's grounding design actually works, not just exists on paper.
- **Orchestrator resilience test**: kill the worker mid-pipeline, restart, assert resume-from-checkpoint (not restart-from-zero) and no duplicate LLM calls for already-completed stages.
- **API-level tests**: auth rejection on missing/invalid key, upload rejection on wrong type/oversized file, 202 + job id returned immediately on valid upload.
- Run the full test suite before every push in Section 12's git workflow, not just before milestone ends.

## 15. Edge Case Checklist
Test these explicitly, don't assume they're covered by the happy path.
- **Upload/parsing**: corrupted file, scanned image-only PDF (no extractable text), empty document, very large document (100+ pages), wrong file extension vs actual content, document with no text (images/diagrams only).
- **Classification/extraction**: ambiguous or multi-subject document, non-English content, document too thin to yield meaningful objectives.
- **Planning**: document too short to justify even one period, document dense enough to imply an unreasonable period count (cap it, don't let the LLM output 40 periods unchecked).
- **Generation**: humanities/narrative content with no "right answer" for assessments — assessment agent must adapt question types, not force numerical problems onto a poem analysis.
- **Validation**: content referencing a concept absent from extracted knowledge (must be flagged, not silently passed); two periods contradicting each other's terminology.
- **Orchestration**: LLM API timeout/rate limit mid-stage, worker crash/restart, duplicate job submission for the same document, concurrent regenerate-section requests on the same TKP.
- **Publishing**: PDF template render failure on unusual content (very long tables, special characters, equations), concurrent writes to the same TKP version.
- Each of these gets a real test case, not a mental note.

## 16. UI Quality Bar
"Simple UI to evaluate gen content" does not mean generic. Avoid default-template look (unstyled shadcn blocks, no visual hierarchy, placeholder-feeling copy).
- Real states for every screen: empty (before upload), loading (with the SSE progress actually reflected, not a spinner lying about state), error (upload failed, stage failed — show which stage and why, not a generic "something went wrong"), success.
- Typography and spacing should be deliberate — pick a type scale and stick to it, don't rely on framework defaults untouched.
- The TKP review screen is the one that matters most: period-by-period navigation, clear separation between generated sections (script vs activities vs assessment), and the regenerate-single-section action visibly scoped to that section, not ambiguous about what it affects.
- No fabricated demo data dressed as real output — if a section fails validation, show that in the UI, don't hide it.

## 17. Client Clarifications (Q&A)

Answers from the client to open questions about scope, gathered 2026-07-31. These refine, not replace, the sections above — where they conflict with an earlier section, this section wins.

1. **Input length/coupling**: primary input is a single chapter or topic. NCERT textbook chapters (Classes 6–12) are the reference benchmark for testing, but the system must not be tightly coupled to NCERT — handle documents of varying length/complexity. Output must be adaptive to the topic (depth, examples, activity style tuned to grade/subject/complexity), never a fixed template. This confirms the existing design (LLM-decided period count, no fixed content templates) — no change needed, but reinforces it as a hard requirement, not a nice-to-have.
2. **Sample docs**: use real NCERT chapter PDFs (Science, Maths, Social Science, Languages) for testing once available, in addition to the synthetic STEM/humanities docs used so far.
3. **Period count/length**: confirmed flexible — no fixed "5×40min" split. The plan should factor in content volume, conceptual complexity, learning objectives, grade level, and recommended pacing. **Action item**: `TeachingPlanOutput`/`Period` currently has no duration/pacing field — add one so periods carry a recommended time estimate, not just a count.
4. **Grounding definition** (this is the important one): all *factual/conceptual* content must trace to the primary source document. Secondary knowledge is allowed, but only for pedagogy — teaching strategies, analogies, classroom activities, assessment framing, learning-science practices — never to introduce new subject matter beyond the source. This confirms the current design: agents cite Stage-3 extracted-knowledge items (which trace to source spans) for *what* is taught, while the delivery mechanism (an analogy, an activity structure, a mnemonic) is free-form and doesn't need its own source span. No change needed — this was already the intended reading of Section 6's grounding requirement, now made explicit.
5. **Pipeline shape**: multi-stage is expected and preferred (confirms current architecture). The client is open to an optional upfront clarifying-questions step (grade, objectives, teaching style, time constraints) if it materially improves output — explicitly framed as "if needed," not mandatory. **Open decision**: whether to build this now or treat classification (Stage 2) as sufficient inference and defer explicit clarifying questions to a later iteration.
6. **Model/provider**: no mandatory provider. Already using Anthropic with tiered routing — this satisfies the requirement as-is, no change needed.
7. **Parsing cost routing**: client explicitly wants a lightweight upfront document-type hint from the user (Mostly Text / Text with Tables / Text with Diagrams-Figures / Text with Equations / Scanned PDF / Not Sure), combined with automatic heuristics (file type, page count, embedded images, OCR signals), to route to cheaper or more advanced parsing. NCERT chapters routinely contain images, diagrams, tables, maps, and equations — current `document_intelligence` only does plain PyMuPDF text extraction with no OCR and no equation/diagram-aware parsing. **Action item**: this is a real gap against the stated benchmark, not just a cost optimization — scanned pages currently degrade silently to near-empty extracted text.

## 18. Architecture Correction: Celery/Redis Removed

Section 7/8 above chose Celery + Redis for orchestration fan-out, with the explicit rationale "reads as real orchestration under evaluation, not a hack." That reasoning assumed a worker process was cheaply deployable. It isn't, on the constraint that actually matters: **Render's Background Worker service type has no free tier at all** (Starter is $7/month minimum), discovered while deploying under a Free-tier-only constraint on 2026-08-01.

Redis's only consumer in this codebase was Celery (broker + result backend) — nothing else read or wrote it. With no free way to run a separate worker, keeping Celery+Redis would mean either paying for a service the project's constraints don't allow, or deploying a worker that never actually runs, silently leaving every job stuck at `pending` forever. Neither is acceptable, and "looks like real orchestration" is not worth a broken deployment.

**Fix**: the pipeline now runs via FastAPI's `BackgroundTasks`, in the same process as the web service. The orchestrator itself — `app/orchestrator/pipeline.py`'s `run_pipeline`/`run_stage`, Postgres-backed checkpointing, retry/backoff, explicit-failure-on-exhaustion — is completely unchanged; only the trigger mechanism changed (`background_tasks.add_task(...)` instead of `run_job.delay(...)`). Sync functions passed to `BackgroundTasks` run in Starlette's threadpool, not the event loop, so this doesn't block concurrent HTTP requests. `celery`, `redis`, the `gyankosh-worker` and `gyankosh-redis` Render services, and `REDIS_URL` are removed entirely — not stubbed out, not left as dead config.

This is a direct instance of Section 2's own instruction ("do not attempt [bonus scope] before the core pipeline is fully working") applied to infrastructure choices too: a custom orchestrator that actually runs for free beats a conventional one that doesn't run at all.