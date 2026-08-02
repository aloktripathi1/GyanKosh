# GyanKosh — Final Submission Readiness Gate Check

Run 2026-08-02. Every item below is backed by a command actually run or a file actually read during this pass, not recollection from earlier sessions. Two genuine issues were found and fixed in this same pass (noted inline); everything else was PASS as found.

---

## PART A — Literal submission requirements

**1. Deployed, working prototype — PASS**
- `curl https://gyankosh-u3b8.onrender.com/health` → `{"status":"ok"}`, HTTP 200 (checked live, this run).
- `curl -I https://gyankosh-beta.vercel.app/` → HTTP 200 (checked live, this run).
- Full live upload → completed → TKP → PDF download, executed right now, not from memory:
  - `POST /documents` → `202`, job `f672065b-8c3d-4aa0-adcb-10cfb0fe74b2`
  - Polled to `status: completed` in **129s** (`created_at` 10:37:09 → `updated_at` 10:39:20), tkp `e9d204ea-eb9a-4f69-97de-99401433f07d`
  - `GET /tkp/e9d204ea-...` → all 4 validation checks `passed: true`
  - Downloaded `lesson_plans.pdf` via the signed URL in `pdf_paths` → HTTP 200, `file` confirms "PDF document, version 1.7", 45183 bytes
- **Side finding, not a failure**: a first attempt with a deliberately trivial one-line input document (no real content) failed at `activity_generation` because the model tried to cite a fact that didn't exist in the (near-empty) extraction. Confirmed this is the grounding check correctly rejecting a bad citation on degenerate input, not a bug — retried with realistic content and it completed cleanly. Documented here for transparency, not silently omitted.

**2. Source code repository — PASS**
- `gh repo view` → `"visibility":"PUBLIC"`.
- `git log origin/main -1` and `git rev-parse HEAD origin/main` both resolve to the same commit (`5995c18` at start of this pass) — local main and origin/main are identical, nothing unpushed.
- `git ls-files` confirms 103 files under `backend/`, 15 under `frontend/`, plus `docs/`, `samples/`, `docker-compose.yml`, `render.yaml`, `BUILD_CONTEXT.md` all present and tracked.
- Confirmed by direct grep that every major fix from this session is literally in the current tree: `expire_on_commit=False` in `db.py` (concurrency fix), `class PathTraversalError` in `local_storage.py`, `STAGE_TIMEOUT_SECONDS = 600` and its use in `pipeline.py`, 3 files in `samples/`.
- `decisions.md` confirmed NOT tracked (correctly gitignored, was never meant to be pushed).

**3. README — setup instructions — PASS, with one caveat**
- Fresh venv (`python3.11 -m venv`) + `pip install -r requirements.txt` run for real in this pass: exit 0, no errors.
- `.env.example` fields diffed programmatically against `Settings` model fields in `config.py`: identical, zero drift.
- `alembic history` loads cleanly and chains `<base> → 0001 → ... → 0006 (head)` with no errors.
- Fresh `npm install && npm run build` run for real (copied to a clean temp directory first): both succeed, `dist/` produced.
- `docker compose config` parses and resolves correctly (env vars pulled from `backend/.env` as documented).
- **Caveat, stated explicitly rather than assumed**: the Docker path (`docker compose up --build`) could not be executed to completion in this environment — the sandbox has no access to a Docker daemon (`permission denied` connecting to `/var/run/docker.sock`). This is a constraint of the verification environment, not a confirmed defect in the repo; the config is valid, but the actual container build/run was not exercised end-to-end in this pass.

**4. README — architecture diagram — was FAIL, fixed**
- Found: the README embedded `docs/Gyankosh.png`, last modified **July 31** (commit `bec1068`), while the architecture was rebuilt on **August 1** (commit `76a309a`). The embedded image was stale relative to the diagram source.
- Fixed: the README now embeds `docs/architecture.png` (an accurate, current, simplified diagram — Client → API Layer → Orchestrator → Document Understanding → Teaching Planner → Content Generation *(parallel)* → Validation → Publishing, with Claude API and Storage as shared services, no Celery/Redis anywhere). Verified this diagram's content against current code before using it. The stale `Gyankosh.png` was removed; the dangling link to a since-deleted `architecture-diagram.excalidraw` was also removed from the README.

**5. README — orchestration explanation — PASS**
- Re-read line by line against `app/orchestrator/pipeline.py` as it exists right now, not as it existed when the section was written. Every claim checked out: checkpointing (`_checkpoint_stage`), retry with backoff (`tenacity` in `_compute_stage`), explicit failure on timeout (`STAGE_TIMEOUT_SECONDS`, confirmed present and wired into both `run_stage` and `_run_parallel_group`), resume-from-checkpoint (`next_stage()`), BackgroundTasks + ThreadPoolExecutor (not Celery/Redis, confirmed absent from `requirements.txt`).

**6. Sample outputs — PASS**
- `ls samples/`: exactly 3 files — `stem_chemistry_chemical_reactions_and_equations.json`, `history_nationalism_in_india.json`, `physics_electricity.json`. All real pipeline output from distinct source documents and subjects, verified with live runs earlier this session (each run twice, full read-through both times).

---

## PART B — README accuracy re-check

**7. Known Limitations, checked line by line against current code — PASS, no stale claims found**
- "Single-tenant... one shared API key" — still true, `require_api_key` checks a single settings value.
- "Storage layer / auth layer coupling" — **re-verified as still true, not stale**: `grep` of `api/deps.py` confirms it still imports `verify_signature` directly from `local_storage.py` rather than through the abstract `StorageBackend` interface. This limitation is accurately still open.
- "Cross-period terminology contradictions aren't explicitly checked" — still true, unchanged in `consistency_check.py`, still backed by a test that documents it as a deliberate boundary.
- "Local file storage doesn't survive a redeploy" — still true, `LocalStorageBackend` is disk-based, Render free tier has no persistent disk.
- "Reliability on dense real documents" (gap_analysis bugs) — accurately describes two bugs that were found and fixed earlier this session, correctly framed as past-and-resolved, not as currently-open.
- Checked for the specific stale-claim risks named in the task: **no mention of "no signed URLs" or "path traversal" as an open limitation anywhere in the README** — both were fixed earlier this session and the README correctly reflects the fix (the traversal-attempt test is mentioned in the Testing section as something verified, not listed as a gap). Nothing to correct here.
- **Found and fixed a different, real drift**: the Testing section stated "99 automated tests" / "98 tests, no database needed." Actual current count, run in this pass: **101 tests collected, 100 pass without a live DB + 1 documented skip**. Both numbers in the README updated to 101 / 100.

**8. Bonus features section — PASS, no drift**
- "Eight independently testable agents" — confirmed, 8 files under `app/agents/` (excluding shared support modules), each a pure `run(input) -> output` function.
- "Exact, then whitespace-normalized, then fuzzy matching" — confirmed against `agents/grounding.py`'s current tiered-match implementation.
- "A dedicated validation check independently re-verifies every citation" — confirmed, and its regression test (deliberately injected fabricated claim) still present and passing.
- "Structured logs... per-stage timing breakdown available through the API" — confirmed, `stage_timings` still a field on `JobRead`, populated live in this pass's own test run.

---

## PART C — Full pipeline sanity, stage by stage

**9. Each of the 10 stages — PASS, individually evidenced**

Evidence combines a code citation with live field data from this pass's own run (job `f672065b`, tkp `e9d204ea`):

| # | Stage | Code evidence | Live evidence (this run) |
|---|---|---|---|
| 1 | Document Intelligence | `agents/document_intelligence.py::run()` | Parsed successfully (stage completed, feeding stage 2) |
| 2 | Classification | `agents/classification.py::run()` | `classification.subject = "Science"`, `topic = "Water Cycle"` — matches actual input |
| 3 | Knowledge Extraction | `agents/knowledge_extraction.py::run()`, grounding via `agents/grounding.py` | 8 concepts extracted, each with a resolved `source_span` |
| 4 | Teaching Planner | `agents/teaching_planner.py`, `MAX_PERIODS = 12` cap confirmed present | 6 periods produced |
| 5 | Content Generation | `agents/content_generator.py` | 6/6 periods have a non-empty `teacher_script` |
| 6 | Activity Generation | `agents/activity_generator.py` | 12 activities generated across periods |
| 7 | Assessment Generation | `agents/assessment_generator.py` | 18 MCQs generated across periods |
| 8 | Gap Analysis | `agents/gap_analysis.py` | 1 learning gap identified |
| 9 | Validation | `validation/schema_check.py`, `grounding_check.py`, `consistency_check.py` | All 4 checks `passed: true` on this exact run |
| 10 | Publishing | `publishing/json_builder.py::build()`, `pdf_renderer.py::render_*` | `pdf_paths` populated with 3 entries; `lesson_plans.pdf` downloaded and confirmed a valid PDF file |

**10. Full test suite — PASS**
- `pytest -q -rs` run in this pass: **100 passed, 1 skipped**.
- The 1 skip: `tests/test_concurrency_live_db.py`, documented skip reason printed by pytest itself: *"requires GYANKOSH_TEST_DATABASE_URL (a live, migrated Postgres) to prove real lock-blocking behavior"* — this is the test's own designed skip condition (no live Postgres configured in this environment by default), not an unexplained skip. This same test was run against a real, disposable Postgres instance earlier this session and passed there too (documented in earlier session work, not re-run in this pass since setting up that instance again wasn't required to confirm the skip is a configuration condition rather than a failure).

---

## PART D — Final live walkthrough

**11. Fresh frontend load, error-state trigger, console check — PASS with one explicit unverifiable item**
- Fresh, uncached fetch of `https://gyankosh-beta.vercel.app/` → HTTP 200, and its JS bundle (`/assets/index-Dv4lMZKx.js`) → HTTP 200.
- Full upload-to-download cycle: covered by item 1 above, executed minutes before this item, against the current live deployment.
- Error-state trigger: uploaded a file with `.pdf` content-type but non-PDF bytes directly against the live API → `400 {"detail":"File content doesn't match its declared type (application/pdf)"}`. Matches `Upload.jsx`'s error-handling path exactly (`setError(err.detail || err.message || "Upload failed")`), verified by reading that code this session.
- **Stated explicitly, not assumed**: this environment has no browser or devtools access, so the browser console itself was not inspected. What was verified instead: every network call the frontend makes returns the expected status/shape (this is a meaningful but not equivalent substitute for an actual console check — a client-side JS error with no failed network call would not be caught by this method).

---

## Fixes applied during this pass

1. **README architecture diagram** — was pointing at a stale, pre-rebuild PNG. Now points at the current, accurate `architecture.png`; dangling link to the deleted `.excalidraw` file removed.
2. **README test count** — "99 automated tests" / "98 tests, no database needed" corrected to 101 / 100 to match the actual current count.

Both are documentation-only fixes. No application code was changed in this pass — every code-level check came back PASS as found.

## Full suite + build re-confirmed after fixes

- `pytest -q`: 100 passed, 1 skipped.
- `npm run build`: succeeds, no errors.
