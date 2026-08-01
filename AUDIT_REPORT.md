# GyanKosh — Architecture & Coverage Audit

Read-only audit against `BUILD_CONTEXT.md`, produced 2026-08-01. No code was changed to produce this report. 48/48 backend tests pass as of this audit.

---

## Section 3 — Functional Requirements (10 stages)

| # | Stage | Status | File(s) | Notes |
|---|---|---|---|---|
| 1 | Document Intelligence | **Implemented** | `agents/document_intelligence.py` | PDF (PyMuPDF)/DOCX/PPTX/TXT parsers, tables, figures, equation regex, per-page OCR fallback (Claude vision) below a text-density threshold, threshold tightened when `document_type_hint=scanned_pdf`. |
| 2 | Educational Classification | **Implemented** | `agents/classification.py`, `schemas/classification.py` | subject, grade, difficulty, topic, chapter, category, language all present. |
| 3 | Knowledge Extraction | **Implemented** | `agents/knowledge_extraction.py`, `agents/grounding.py` | objectives/prerequisites/concepts/definitions/formulae/keywords/examples/applications/misconceptions all present; every item resolves a `source_span` via `resolve_grounding_refs` (exact → whitespace-normalized → rapidfuzz fallback). Ungrounded items are dropped individually rather than failing the whole batch (`test_knowledge_extraction_drops_ungrounded_items_without_failing_the_batch`). |
| 4 | Teaching Planner | **Partial** | `agents/teaching_planner.py`, `schemas/teaching_planner.py` | LLM decides period count and per-period `recommended_duration_minutes` (not fixed). **Missing**: no upper-bound cap on period count — Section 15 explicitly calls this out ("cap it, don't let the LLM output 40 periods unchecked") and there is no code enforcement or test. |
| 5 | Classroom Content Generation | **Implemented** | `agents/content_generator.py`, `schemas/content_generator.py` | Entry ticket, teacher script, blackboard notes, activities-in-content, checkpoint questions, exit ticket, homework, mentor moment all present per period, all grounded. |
| 6 | Activity Generation | **Implemented** | `agents/activity_generator.py` | type/duration/materials/instructions/success criteria present, grounded. |
| 7 | Assessment Generation | **Partial** | `agents/assessment_generator.py` | MCQ/short/long/numerical + answer keys/rubrics present and grounded. **Missing**: no test proving the humanities-adaptation requirement from Section 15 ("assessment agent must adapt question types, not force numerical problems onto a poem analysis") — there is no fixture/assertion checking that a narrative/humanities input yields non-numerical-heavy output. |
| 8 | Learning Gap Analysis | **Implemented** | `agents/gap_analysis.py` | misconceptions, diagnostic questions, severity, remediation present, grounded. |
| 9 | Validation | **Partial** | `validation/schema_check.py`, `grounding_check.py`, `consistency_check.py` | Grounding check is thorough (re-verifies every source_span against Stage 3, independent of agent-time resolution). **Gap**: `pipeline.py::_run_validation` only runs `schema_check` against the **classification** output — none of the other 6 stage outputs get an explicit schema-check entry in the report (they're implicitly schema-valid by having loaded successfully via `_load()`, but the report field is misleadingly narrow — it reads as "schema check" but only ever checks one of seven schemas). Consistency check explicitly does *not* check cross-period terminology contradiction (Section 15's example) — the code comment argues this is "structurally prevented" by grounding-by-reference, which is a reasonable argument but is untested, not proven. |
| 10 | Publishing | **Implemented** | `publishing/json_builder.py`, `publishing/pdf_renderer.py` | TKP.json assembly + 3 WeasyPrint PDFs (lesson plans, teacher guide, assessment book), exposed via `GET /tkp/{id}` and `GET /files/{path}`. |

Plus streaming progress API: **Implemented** — `GET /jobs/{id}/stream` (SSE via polling, see Section 4 below).

---

## Section 4 — Non-Functional Requirements

| NFR | Status | Evidence |
|---|---|---|
| Checkpoint/resume | **Implemented** | `pipeline.py::next_stage()` resumes from first uncheckpointed stage; `test_resume_from_checkpoint_skips_completed_stages_and_no_duplicate_calls` proves no duplicate LLM calls on resume. |
| Retry w/ backoff, explicit failure | **Implemented** | `tenacity.Retrying` (3 attempts, exponential backoff) in `_compute_stage`; `test_stage_retries_then_succeeds` and `test_stage_fails_explicitly_after_exhausting_retries` both pass. |
| Progress visibility (SSE) | **Implemented, with a caveat** | `GET /jobs/{id}/stream` works and streams real state — but it's a 2-second DB-poll loop, not push-based. This is functionally fine (satisfies "not blank-screen polling-only UX" since it *is* pushed to the client via SSE), but `orchestrator/progress.py` contains a dead, never-called `stream_job_progress()` function whose docstring says "Implemented in Milestone 4" and raises `NotImplementedError` — a stale placeholder from before the polling approach was finalized as the real implementation. It doesn't affect behavior (nothing calls it) but is orphaned code + a misleading comment. |
| Cost control (model tiering + caching) | **Implemented** | `llm/client.py`: `ModelTier.CHEAP` (Haiku) for classification/extraction, `ModelTier.STRONG` (Sonnet) for planning/content/activity/assessment/gap; every call marks the system prompt `cache_control: ephemeral`. Document-hash-based caching of stages 1-3 on re-upload confirmed in `api/documents.py::_find_cached_stage_results` and tested (`test_progress_reflects_precached_stages_from_document_hash_reuse`). |
| Groundedness | **Implemented, well-tested** | Tiered match (exact → whitespace-normalized → rapidfuzz ≥85) in `agents/grounding.py`; independent re-check in `validation/grounding_check.py`; `test_grounding_check_flags_deliberately_injected_ungrounded_claim` proves the check actually catches a real injected violation, not just green-lighting everything. |
| Modularity | **Implemented** | Every agent is a standalone `run(input) -> Output` function (verified below, Section 10). No orchestrator logic found leaking into API routes (`grep` for stage-dispatch calls in `api/*.py` returned nothing). |
| Security | **Partial — one real finding** | API-key auth present and consistently applied (`require_api_key` dependency on every route except file downloads, which additionally accept a query param for browser-navigation reasons). Upload validates Content-Type and 25MB size cap. **Two gaps**: (1) `storage/local_storage.py::_resolve()` does `self.base_path / storage_path` with no path-traversal normalization — a `path` value containing `../` segments passed to `GET /files/{path:path}` is not blocked before `open()`, which is a real (if API-key-gated) path traversal exposure, not just a theoretical one. (2) Section 4 explicitly calls for "signed/expiring URLs for generated PDFs" — the actual implementation reuses the same static, non-expiring `API_KEY` as a query param; `local_storage.py::url()`'s own comment admits "expiry is not enforced here." This is a legitimate scope-documented gap (comment says it becomes real once S3 is swapped in) but the spec's exact NFR wording isn't met today. |

---

## Section 5 — Core Entities vs actual DB schema

| Table | Spec | Actual | Drift |
|---|---|---|---|
| `documents` | id, filename, file_type, storage_path, uploaded_at | + `content_hash` (indexed), `document_type_hint` | Both additions are load-bearing (content-hash caching, Section 17 Q&A #7's parser-routing hint) — reasonable, necessary drift, not a defect. |
| `jobs` | id, document_id, status, current_stage, progress_pct, error, stage_results, created_at, updated_at | + `teaching_context` | Supports Section 17 Q&A's optional free-text teaching context — reasonable drift. |
| `tkp_versions` | id, job_id, version, classification, extracted_knowledge, teaching_plan, period_content, assessments, learning_gaps, validation_report, published_at | + `activities` (separate from `period_content`), `pdf_paths` | `activities` as its own column is more correct than the spec's implicit merge, since Stage 6 (Activity Generation) is a distinct stage per Section 3. `pdf_paths` is required for Stage 10's PDF exposure and simply wasn't itemized in the original spec's shorthand table. Both are necessary, not scope creep. |

No missing columns. All drift is additive and justified.

---

## Section 6 — Architecture diagram vs actual

The diagram (and Section 7/8) describe Celery + Redis fan-out for the parallel generation stages. **This was removed** (documented already in `BUILD_CONTEXT.md` Section 18, and in the untracked `decisions.md`) because Render's free tier has no Background Worker option at all. The actual architecture runs the pipeline via FastAPI `BackgroundTasks` in the same web process, with true concurrency for the independent generation stages implemented via `ThreadPoolExecutor` inside `pipeline.py::_run_parallel_group` rather than Celery fan-out. This is a self-acknowledged, documented deviation with a clear forcing reason — not an oversight. Every other component in the diagram (API layer, orchestrator, agents, validation, publishing, storage) matches the actual structure 1:1.

---

## Section 7 — Key Decisions: were they actually followed?

| Decision | Actually followed? |
|---|---|
| Custom orchestrator + Celery/Redis | **Partially superseded** — custom orchestrator: yes, exactly as designed. Celery/Redis: no, removed (Section 18, justified). |
| Async job pattern, 202 + poll/stream | **Yes** — `POST /documents` returns 202 immediately (`test_full_pipeline_completes...` and manual production tests confirm). |
| SSE progress | **Yes**, via polling (see Section 4 caveat above). |
| Postgres + JSONB | **Yes**, exactly as designed. |
| LLM routing (cheap/strong split) | **Yes**, exactly as designed. |
| Structured output on every LLM call | **Yes, with one clean exception**: `ocr_page_text()` in `llm/client.py` is a free-text vision call (transcribing a scanned page to plain text), not tool-use/schema-bound. This is correct behavior, not a violation — OCR output isn't meant to be a structured object, it's raw text fed into the *next* structured call. Every call that actually produces stage output uses forced tool-use. |
| Grounding-by-reference validation | **Yes**, exactly as designed, and independently re-verified in the Validation Engine rather than trusted from agent-time resolution alone. |
| REST API | **Yes**. |
| Single API key auth | **Yes**, but see the two Section 4 security gaps above (path traversal, non-expiring file URLs) — the *auth model* is as designed, but two supporting security properties implied by Section 4 aren't fully met. |
| Deployment: Render (backend+worker+Postgres+Redis) + Vercel | **Partially superseded** — Render backend+Postgres: yes. Worker+Redis: removed. Frontend: Vercel, as planned (an earlier Netlify attempt was abandoned before going live). |
| WeasyPrint PDF | **Yes**. |
| Storage interface-abstracted | **Yes** — confirmed no direct filesystem/S3 calls outside `storage/base.py` and its one implementation; the two direct-file-access hits found via grep (`fitz.open(stream=...)` and a `Path(__file__).parent / "templates"` for bundled PDF templates) are both benign, not storage-bypasses. |

---

## Section 9 — Folder structure diff

Actual structure matches the spec almost exactly. Notable differences:
- `backend/app/agents/document_type_hints.py` and `backend/app/agents/grounding.py` — not itemized in the spec's agent list, but both are legitimate shared support modules (hint constants, grounding resolution used by every generation agent), not scope creep.
- `backend/app/orchestrator/regenerate.py` and `backend/app/orchestrator/stage_runners.py` — not in the spec's two-file orchestrator listing (`pipeline.py`, `progress.py`), but both are real, necessary additions: `regenerate.py` implements the single-section regenerate endpoint (`POST /tkp/{id}/regenerate/{section}`), which the spec's own Section 6 architecture diagram requires; `stage_runners.py` is a dedup layer shared between `pipeline.py` and `regenerate.py` (see `decisions.md` #16).
- `backend/app/tasks/celery_app.py` — correctly **absent** (removed per Section 18).
- `/samples` — **present as a directory but empty except for `.gitkeep`**. This is a direct, unambiguous miss against both Section 9 ("min 2 sample TKP.json for submission") and Section 13's Definition of Done. Flagged prominently in the priority list below — this is a zero-code-risk, high-visibility fix.
- `docs/README.md` exists and is reasonably current (Status section reflects the BackgroundTasks pivot). `docs/architecture-diagram.excalidraw` and `docs/Gyankosh.png` both exist.

---

## Section 10 — Coding conventions spot-check

- **Agent pure-function contract**: confirmed for all 8 agents — every one is `run(input) -> Output`, no side effects beyond the LLM call (verified via signature grep + reading `document_intelligence.py`, `classification.py`, `teaching_planner.py` in full). No DB session, no storage write, no HTTP call to anything but the Anthropic client, inside any agent module.
- **Orchestrator-owned retries**: confirmed — no agent module contains its own retry loop; all retry/backoff lives in `pipeline.py::_compute_stage`.
- **No direct filesystem/S3 calls outside `storage/base.py`**: confirmed, see Section 7 above.
- **No orchestrator logic in API routes**: confirmed via grep — `api/documents.py` calls `background_tasks.add_task(run_job_in_background, ...)` and nothing more; no direct stage dispatch anywhere in `api/`.
- **Config via `.env` + pydantic-settings**: confirmed, and `REDIS_URL` correctly absent per Section 18's note. One residual issue: `requirements.txt` still lists `asyncpg==0.29.0`, which is dead weight — the app uses the sync `psycopg2` driver (`DATABASE_URL` is `postgresql+psycopg2://...` throughout), and `asyncpg` doesn't appear anywhere in `app/` or `alembic/`. Minor, but it's an unused dependency that should be removed in the cleanup pass.

---

## Section 14 — Testing strategy: what exists, what doesn't

| Requirement | Status |
|---|---|
| Unit tests per agent (mock LLM, assert schema) | **Implemented** — `test_agents_llm.py` covers all 7 non-document-intelligence agents; `test_document_intelligence.py` covers OCR fallback branching. |
| Fixture/golden tests (3 fixed docs: STEM, humanities, messy — full pipeline, assert clean/graceful outcomes) | **Missing.** There is no fixtures directory and no test that runs 3 fixed documents through the full pipeline asserting the specific behaviors called for (clean validation report on STEM/humanities, graceful low-confidence flag — not a crash — on the messy one). `test_orchestrator.py`'s full-pipeline test uses fully-mocked stub agents, not real fixture documents, and doesn't test the "messy document" graceful-degradation case at all. This is the single most direct testing gap against Section 14's own wording. |
| Grounding regression test | **Implemented** — `test_grounding_check_flags_deliberately_injected_ungrounded_claim` in `test_validation.py`, exactly as specified. |
| Orchestrator resilience test (kill mid-pipeline, resume, no duplicate calls) | **Implemented** — `test_resume_from_checkpoint_skips_completed_stages_and_no_duplicate_calls` in `test_orchestrator.py`. |
| API-level tests (auth rejection, upload rejection, 202+job_id) | **Missing.** Only `test_health.py` exercises `TestClient`, and only against `/health`. There is no test asserting: 401 on missing/invalid `x-api-key`, 415 on wrong content-type, 413 on oversized upload, or 202+`job_id` on a valid upload. This is explicitly named in Section 14 and currently has zero coverage. |
| Run full suite before every push | Can't verify historically, but the suite is fast (1.5s, 48 tests) and clearly has been kept green — no currently-failing tests. |

---

## Section 15 — Edge case checklist (exact status, not rounded up)

| Edge case | Test exists? | Status |
|---|---|---|
| Corrupted file | **No** | `fitz.open()` on invalid PDF bytes will raise; this propagates through `_compute_stage`'s retry loop (3 attempts, all doomed to fail identically) before the job is marked `failed` with the raw PyMuPDF error as `job.error`. Functionally "fails explicitly, not silently" per Section 4, but there's no test proving this, no upload-time content-sniffing rejection, and 3 pointless retries elapse first. |
| Scanned image-only PDF (no extractable text) | **Yes** | `test_low_text_page_falls_back_to_ocr` — passes. |
| Empty document | **No** | No test for a zero-byte or whitespace-only upload. `_parse_txt` would produce an empty `raw_text`; downstream agent behavior on empty extracted text is unverified. |
| Very large document (100+ pages) | **No** | `MAX_UPLOAD_BYTES` (25MB) bounds file size but not page count or wall-clock processing time. No test exercises a 100+ page document; per-page OCR fallback in the worst case (every page below the text threshold) has no timeout/circuit-breaker distinct from the per-stage retry logic. |
| Wrong file extension vs actual content | **No** | `documents.py` trusts the browser-supplied `Content-Type` header only — no magic-byte sniffing. A `.txt` file relabeled with a PDF content-type (or vice versa) would be routed to the wrong parser and likely crash ungracefully rather than being caught explicitly. |
| Document with no text (images/diagrams only) | **Partial** | Covered by the OCR-fallback path if every page trips the low-text threshold, but there's no test for the terminal case where OCR *also* returns nothing usable (e.g. a truly blank scanned page) all the way through to a graceful downstream flag rather than empty/hallucinated extraction. |
| Ambiguous/multi-subject document | **No** | No test. |
| Non-English content | **No** | `classification` schema captures `language`, but nothing downstream is tested for non-English input behavior. |
| Document too thin for meaningful objectives | **No** | No test. |
| Document too short to justify even one period | **No** | No test. |
| Period count cap (dense doc → unreasonable period count) | **No — and no code enforcement either** | Confirmed via reading `teaching_planner.py`, its prompt, and `schemas/teaching_planner.py`: no numeric cap in the prompt, no `max_length` on the `periods` list, no post-generation clamp. This is a direct, explicit spec action item that is simply not implemented, not just untested. |
| Humanities content: assessment adapts question types | **No** | No test proving non-numerical-heavy output for narrative input, despite `assessment_generator.py` prompt likely handling this in practice (untested claim, not verified). |
| Content referencing a concept absent from extracted knowledge (must be flagged) | **Yes** | Covered by `test_grounding_check_flags_deliberately_injected_ungrounded_claim`. |
| Two periods contradicting each other's terminology | **No** | `consistency_check.py` explicitly does not check this (see Section 3 table); the code's own docstring argues it's structurally prevented, but that argument is untested. |
| LLM API timeout/rate limit mid-stage | **Partial** | Generic retry/backoff via `tenacity` covers this at the mechanism level (any exception triggers retry), and `REQUEST_TIMEOUT_SECONDS=120` bounds a stalled call. No test specifically simulates a rate-limit (429) response, and there's no `Retry-After`-aware backoff — acceptable per spec wording ("retry 2-3x with backoff"), just not rate-limit-specific. |
| Worker crash/restart | **Yes** | `test_resume_from_checkpoint_skips_completed_stages_and_no_duplicate_calls`. |
| Duplicate job submission for the same document | **Partial** | `_find_cached_stage_results` reuses stages 1-3's output on a repeat upload of identical bytes, but a **new** `Job` row is still created every time — two near-simultaneous uploads of the same document would each independently run stages 4+ (content/activity/assessment/gap generation), duplicating LLM spend for that portion. No test, and the caching is a cost optimization, not actual duplicate-submission rejection. |
| Concurrent regenerate-section requests on the same TKP | **No — and no code guard either** | Confirmed via reading `regenerate.py`: no row lock, no optimistic-concurrency version check. Two concurrent regenerate calls on the same `TKPVersion` (even for different sections) race on `db.commit()`; the recomputed `validation_report` for whichever commits second may be based on a stale read of the section the other request just changed. Real, unguarded race condition. |
| PDF render failure on unusual content (long tables, special chars, equations) | **No** | No test. |
| Concurrent writes to the same TKP version | **No** | Same underlying gap as the regenerate race above — no locking anywhere in `tkp_version` writes. |

**Summary: of 20 listed edge cases, 4 are tested (Implemented), 4 are partial, 12 have no test at all** — and two of those twelve (period-count cap, concurrent regenerate) also have no code-level protection, not just missing tests.

---

## Section 16 — UI quality bar

| Requirement | Status |
|---|---|
| Real empty/loading/error/success states | **Implemented** — `Upload.jsx` has explicit `idle/uploading/error` states with a real error banner (not generic); `JobProgress.jsx` reflects actual SSE stage data (not a lying spinner) and has a distinct failed-state banner naming which stage(s) failed and why; `TKPReview.jsx` has skeleton loading states and a distinct error state separate from the loaded-content state. |
| Deliberate typography/spacing, not framework defaults | **Implemented** — custom type scale, warm/editorial visual language (serif display font, custom card/badge/stepper components), confirmed via `styles.css` read and the two screenshots reviewed in this session — this is clearly not an untouched shadcn/Tailwind default look. |
| TKP review: period-by-period nav, clear section separation, scoped regenerate | **Implemented** — tabbed nav (Overview / Period N / Learning Gaps), each section (`Classification`, `Extracted Knowledge`, `Teaching Plan`, per-period content/activities/assessments) has its own `SectionHeader` with a `Regenerate` button scoped via an explicit `section` prop passed straight to `POST /tkp/{id}/regenerate/{section}` — not ambiguous about scope. |
| No fabricated demo data; validation failures shown, not hidden | **Implemented** — `ValidationBadge`/`ValidationDetail` render real pass/fail state per check type, with the actual violation/missing-item/conflict list surfaced, not suppressed. |

No gaps found against Section 16 in this audit.

---

## Prioritized Gap List (ranked by rubric weight, highest first)

Rubric: Content Generation 25% · Educational Understanding 20% · Teaching Planning 20% · Document Intelligence 15% · Engineering 15% · Docs 5%

### Teaching Planning (20%) — highest-priority functional gap
1. **No period-count cap.** Explicit spec action item, zero code enforcement, zero test. A dense document could produce an unreasonable number of periods with nothing stopping it. This is the single highest-value functional fix available — it's both a real robustness gap and a named rubric-adjacent requirement.

### Content Generation (25%) — untested, not necessarily broken
2. **No test proving humanities/narrative assessment adaptation.** The 25%-weighted category's most distinctive edge case (per Section 15) has no automated proof it works, only informal confidence from manual testing earlier in the build.
3. **`schema_check` in the validation report only covers Classification**, not the other 6 stage outputs — the report field is misleadingly narrow for a category graders will likely inspect closely (the validation report is the most visible "does this actually work" artifact).

### Educational Understanding (20%)
4. **No tests for ambiguous/multi-subject, non-English, or thin-content documents** — all explicitly named Section 15 cases with zero coverage. Educational Understanding is exactly the category these would validate.

### Document Intelligence (15%)
5. **No corrupted-file, empty-document, oversized-document, or wrong-extension-vs-content tests**, and the wrong-extension case has no real defense (Content-Type header trust only, no magic-byte check). Four of Section 15's six Document Intelligence edge cases are completely uncovered.

### Engineering (15%)
6. **Zero API-level tests** — explicitly required by Section 14, currently absent entirely (auth rejection, upload validation, 202 response).
7. **Path traversal vulnerability** in `storage/local_storage.py::_resolve()` — real, exploitable (with a valid API key) security defect, not just a missing test.
8. **Concurrent regenerate-section race condition** — no locking, explicitly named in Section 15, currently unguarded.
9. **No golden 3-fixture (STEM/humanities/messy) pipeline test** — explicitly required by Section 14, currently absent.
10. Minor: dead `stream_job_progress()` function + stale "Milestone 4" comments in `progress.py`/`jobs.py`; unused `asyncpg` dependency. Low-risk, cheap cleanup-pass items.

### Docs (5%) — lowest weight, but zero-cost to fix and highly visible
11. **`/samples` is empty.** Explicit Definition-of-Done and folder-structure requirement. This is the cheapest possible fix on this entire list (copy 2 already-generated real `TKP.json` outputs from this session's test runs into the folder) and its absence is exactly the kind of thing a grader notices in under 10 seconds of opening the repo.

---

## What this audit deliberately did not do

Per the instruction, this pass made no code changes, ran no new tests, and did not attempt fixes. Pass 2 (fill Section 15 gaps with real tests, add the two missing Section 14 test types, confirm STEM/humanities fixture runs) and Pass 3 (cleanup, convention enforcement, naming pass, dependency pruning) are scoped and ready to start on your go-ahead, in that order.
