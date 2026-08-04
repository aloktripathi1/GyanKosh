import logging
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError, as_completed

from sqlalchemy.orm import Session
from tenacity import Retrying, stop_after_attempt, wait_exponential

from app.agents import document_intelligence
from app.models.document import Document
from app.models.job import STAGE_NAMES, Job, JobStatus
from app.models.tkp_version import TKPVersion
from app.orchestrator import progress, stage_runners
from app.publishing import json_builder
from app.publishing.pdf_renderer import render_assessment_book, render_lesson_plans, render_teacher_guide
from app.schemas.activity_generator import ActivityGenerationOutput
from app.schemas.assessment_generator import AssessmentGenerationOutput
from app.schemas.classification import ClassificationOutput
from app.schemas.content_generator import PeriodContentOutput
from app.schemas.document_intelligence import DocumentIntelligenceOutput
from app.schemas.gap_analysis import GapAnalysisOutput
from app.schemas.knowledge_extraction import KnowledgeExtractionOutput
from app.schemas.teaching_planner import TeachingPlanOutput
from app.schemas.validation import ValidationReport
from app.storage import get_storage
from app.storage.base import StorageBackend
from app.validation import consistency_check, grounding_check, schema_check

logger = logging.getLogger("gyankosh.orchestrator")

MAX_RETRIES = 3
BACKOFF_BASE_SECONDS = 2
# Safety net, not the primary defense: MAX_RETRIES attempts at
# REQUEST_TIMEOUT_SECONDS (120s) each plus backoff already bounds a *normal*
# worst case around 6 minutes. This catches abnormal hangs that wouldn't
# resolve on their own at all — e.g. multiple threads contending for one
# SQLAlchemy Session concurrently (see db.py's expire_on_commit=False for the
# actual fix to that specific case) — so a stage fails explicitly instead of
# leaving a job "running" forever.
STAGE_TIMEOUT_SECONDS = 600

# content/activity/assessment generation and gap analysis each depend only on
# the teaching plan and/or knowledge extraction, never on each other — running
# them concurrently overlaps their LLM latency instead of paying for it 4x.
PARALLEL_STAGE_GROUP = frozenset(
    {"content_generation", "activity_generation", "assessment_generation", "gap_analysis"}
)


class StageFailedError(Exception):
    def __init__(self, stage: str, cause: Exception):
        self.stage = stage
        self.cause = cause
        super().__init__(f"Stage '{stage}' failed after {MAX_RETRIES} attempts: {cause}")


def next_stage(job: Job) -> str | None:
    """Resume point: first stage in STAGE_NAMES not yet checkpointed."""
    for stage in STAGE_NAMES:
        if stage not in job.stage_results:
            return stage
    return None


def _load(job: Job, stage: str, schema):
    return schema.model_validate(job.stage_results[stage])


def _execute_stage(job: Job, stage: str, document: Document, storage: StorageBackend, db: Session) -> dict:
    """Build the stage's input from prior checkpointed results and call its
    agent. Pure dispatch — no retry or commit here, that belongs to run_stage."""
    if stage == "document_intelligence":
        content = storage.read(document.storage_path)
        di_input = document_intelligence.DocumentIntelligenceInput(
            str(document.id), document.file_type, content, document.document_type_hint
        )
        result = document_intelligence.run(di_input)
        return result.model_dump(mode="json")

    if stage == "classification":
        doc_intel = _load(job, "document_intelligence", DocumentIntelligenceOutput)
        return stage_runners.run_classification(doc_intel, job.teaching_context)

    if stage == "knowledge_extraction":
        doc_intel = _load(job, "document_intelligence", DocumentIntelligenceOutput)
        return stage_runners.run_knowledge_extraction(doc_intel)

    if stage == "teaching_planner":
        cls = _load(job, "classification", ClassificationOutput)
        ek = _load(job, "knowledge_extraction", KnowledgeExtractionOutput)
        return stage_runners.run_teaching_planner(cls, ek, job.teaching_context)

    if stage == "content_generation":
        plan = _load(job, "teaching_planner", TeachingPlanOutput)
        ek = _load(job, "knowledge_extraction", KnowledgeExtractionOutput)
        language = _load(job, "classification", ClassificationOutput).language
        return stage_runners.run_content_generation(plan, ek, language)

    if stage == "activity_generation":
        plan = _load(job, "teaching_planner", TeachingPlanOutput)
        ek = _load(job, "knowledge_extraction", KnowledgeExtractionOutput)
        language = _load(job, "classification", ClassificationOutput).language
        return stage_runners.run_activity_generation(plan, ek, language)

    if stage == "assessment_generation":
        plan = _load(job, "teaching_planner", TeachingPlanOutput)
        ek = _load(job, "knowledge_extraction", KnowledgeExtractionOutput)
        language = _load(job, "classification", ClassificationOutput).language
        return stage_runners.run_assessment_generation(plan, ek, language)

    if stage == "gap_analysis":
        ek = _load(job, "knowledge_extraction", KnowledgeExtractionOutput)
        language = _load(job, "classification", ClassificationOutput).language
        return stage_runners.run_gap_analysis(ek, language)

    if stage == "validation":
        return _run_validation(job).model_dump(mode="json")

    if stage == "publishing":
        return _run_publishing(job, storage, db)

    raise ValueError(f"Unknown stage: {stage}")


def _run_validation(job: Job) -> ValidationReport:
    cls = _load(job, "classification", ClassificationOutput)
    ek = _load(job, "knowledge_extraction", KnowledgeExtractionOutput)
    plan = _load(job, "teaching_planner", TeachingPlanOutput)
    content = _load(job, "content_generation", PeriodContentOutput)
    activities = _load(job, "activity_generation", ActivityGenerationOutput)
    assessments = _load(job, "assessment_generation", AssessmentGenerationOutput)
    gaps = _load(job, "gap_analysis", GapAnalysisOutput)

    schema_result = schema_check.check(cls.model_dump(mode="json"), ClassificationOutput)
    return ValidationReport(
        schema_check=schema_result,
        grounding_check=grounding_check.check(ek, content, activities, assessments, gaps),
        completeness_check=consistency_check.check_completeness(plan, content, activities, assessments),
        consistency_check=consistency_check.check_consistency(plan, content, activities, assessments),
    )


def _run_publishing(job: Job, storage: StorageBackend, db: Session) -> dict:
    tkp = json_builder.build(str(job.id), version=1, stage_results=job.stage_results)

    pdf_paths = {
        "lesson_plans": render_lesson_plans(tkp, storage),
        "teacher_guide": render_teacher_guide(tkp, storage),
        "assessment_book": render_assessment_book(tkp, storage),
    }

    tkp_version = TKPVersion(
        job_id=job.id,
        version=tkp.version,
        classification=tkp.classification.model_dump(mode="json"),
        extracted_knowledge=tkp.extracted_knowledge.model_dump(mode="json"),
        teaching_plan=tkp.teaching_plan.model_dump(mode="json"),
        period_content=tkp.period_content.model_dump(mode="json"),
        activities=tkp.activities.model_dump(mode="json"),
        assessments=tkp.assessments.model_dump(mode="json"),
        learning_gaps=tkp.learning_gaps.model_dump(mode="json"),
        validation_report=tkp.validation_report.model_dump(mode="json"),
        pdf_paths=pdf_paths,
        published_at=tkp.published_at,
    )
    db.add(tkp_version)
    db.flush()

    return {"tkp_version_id": str(tkp_version.id), "pdf_paths": pdf_paths}


def _compute_stage(db: Session, job: Job, stage: str, document: Document, storage: StorageBackend) -> tuple[dict, float]:
    """Run one stage's agent with retry/backoff and return (result, duration_seconds).
    No DB writes happen here — this is the half of stage execution that's safe to
    call from a worker thread, so the parallel group can run several of these
    concurrently before checkpointing any of them."""
    job_id = str(job.id)
    start = time.monotonic()
    attempt_count = 0
    try:
        result = None
        for attempt in Retrying(
            stop=stop_after_attempt(MAX_RETRIES),
            wait=wait_exponential(multiplier=BACKOFF_BASE_SECONDS, min=BACKOFF_BASE_SECONDS),
            reraise=True,
        ):
            with attempt:
                attempt_count += 1
                if attempt_count > 1:
                    logger.warning(
                        f"retrying (attempt {attempt_count}/{MAX_RETRIES})",
                        extra={"job_id": job_id, "stage": stage},
                    )
                result = _execute_stage(job, stage, document, storage, db)
    except Exception as e:  # noqa: BLE001 - any stage failure is retryable, then explicit
        duration_ms = int((time.monotonic() - start) * 1000)
        logger.error(
            f"stage failed after {attempt_count} attempt(s): {e}",
            extra={"job_id": job_id, "stage": stage, "duration_ms": duration_ms},
        )
        raise StageFailedError(stage, e) from e

    duration = time.monotonic() - start
    logger.info(
        f"stage completed (attempt {attempt_count}/{MAX_RETRIES})",
        extra={"job_id": job_id, "stage": stage, "duration_ms": int(duration * 1000)},
    )
    return result, duration


def _checkpoint_stage(db: Session, job: Job, stage: str, result: dict, duration_seconds: float) -> None:
    job.stage_results = {**job.stage_results, stage: result}
    job.stage_timings = {**job.stage_timings, stage: round(duration_seconds, 2)}
    completed = sum(1 for s in STAGE_NAMES if s in job.stage_results)
    progress.emit(db, job, stage, int(completed / len(STAGE_NAMES) * 100))


def run_stage(db: Session, job: Job, stage: str, document: Document, storage: StorageBackend) -> None:
    """Execute one stage with retry/backoff, checkpoint the result on success, and
    mark the job failed (explicitly, never silently) on exhaustion — including
    on an outright hang, not just a raised exception."""
    job_id = str(job.id)
    pool = ThreadPoolExecutor(max_workers=1)
    try:
        future = pool.submit(_compute_stage, db, job, stage, document, storage)
        try:
            result, duration = future.result(timeout=STAGE_TIMEOUT_SECONDS)
        except FutureTimeoutError:
            logger.error(
                f"stage timed out after {STAGE_TIMEOUT_SECONDS}s (still running in the background, abandoning)",
                extra={"job_id": job_id, "stage": stage},
            )
            e = StageFailedError(stage, TimeoutError(f"exceeded {STAGE_TIMEOUT_SECONDS}s stage timeout"))
            job.status = JobStatus.FAILED
            job.error = str(e)
            db.commit()
            raise e from None
        except StageFailedError as e:
            job.status = JobStatus.FAILED
            job.error = str(e)
            db.commit()
            raise
    finally:
        pool.shutdown(wait=False)  # a genuinely hung worker thread can't be killed; don't block on it
    _checkpoint_stage(db, job, stage, result, duration)


def _run_parallel_group(db: Session, job: Job, document: Document, storage: StorageBackend) -> None:
    """Run every not-yet-checkpointed stage in PARALLEL_STAGE_GROUP concurrently.
    Stages that succeed are checkpointed even if a sibling stage fails, so a
    resumed run doesn't redo work that already completed."""
    pending = [s for s in STAGE_NAMES if s in PARALLEL_STAGE_GROUP and s not in job.stage_results]
    if not pending:
        return

    job.current_stage = "+".join(pending)
    db.commit()

    first_error: StageFailedError | None = None
    pool = ThreadPoolExecutor(max_workers=len(pending))
    futures = {pool.submit(_compute_stage, db, job, stage, document, storage): stage for stage in pending}
    try:
        for future in as_completed(futures, timeout=STAGE_TIMEOUT_SECONDS):
            stage = futures[future]
            try:
                result, duration = future.result()
            except StageFailedError as e:
                first_error = first_error or e
                continue
            _checkpoint_stage(db, job, stage, result, duration)
    except FutureTimeoutError:
        stuck = [stage for future, stage in futures.items() if not future.done()]
        logger.error(
            f"parallel batch timed out after {STAGE_TIMEOUT_SECONDS}s, still running: {stuck}",
            extra={"job_id": str(job.id), "stage": "+".join(stuck)},
        )
        first_error = first_error or StageFailedError(
            "+".join(stuck), TimeoutError(f"exceeded {STAGE_TIMEOUT_SECONDS}s stage timeout: {stuck}")
        )
    finally:
        pool.shutdown(wait=False)  # a genuinely hung worker thread can't be killed; don't block on it

    if first_error is not None:
        job.status = JobStatus.FAILED
        job.error = str(first_error)
        db.commit()
        raise first_error


def run_pipeline(db: Session, job: Job) -> None:
    """Drive the job from its current checkpoint to completion, one stage at a
    time. Safe to call repeatedly on the same job: next_stage() always resumes
    from the first uncompleted stage rather than restarting."""
    document = db.get(Document, job.document_id)
    storage = get_storage()
    job_id = str(job.id)
    pipeline_start = time.monotonic()
    logger.info("pipeline started", extra={"job_id": job_id})

    job.status = JobStatus.RUNNING
    # Stages can arrive pre-checkpointed (document-hash cache reuse on upload),
    # so progress must reflect them even though they never went through
    # run_stage/progress.emit here.
    already_done = sum(1 for s in STAGE_NAMES if s in job.stage_results)
    job.progress_pct = max(job.progress_pct, int(already_done / len(STAGE_NAMES) * 100))
    db.commit()

    stage = next_stage(job)
    while stage is not None:
        if stage in PARALLEL_STAGE_GROUP:
            _run_parallel_group(db, job, document, storage)
        else:
            job.current_stage = stage
            db.commit()
            run_stage(db, job, stage, document, storage)
        stage = next_stage(job)

    job.status = JobStatus.COMPLETED
    job.progress_pct = 100
    db.commit()
    total_ms = int((time.monotonic() - pipeline_start) * 1000)
    logger.info(f"pipeline completed in {total_ms}ms", extra={"job_id": job_id, "duration_ms": total_ms})
