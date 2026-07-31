import time

from sqlalchemy.orm import Session

from app.agents import activity_generator, assessment_generator, classification as classification_agent
from app.agents import content_generator, document_intelligence, gap_analysis, knowledge_extraction, teaching_planner
from app.models.document import Document
from app.models.job import STAGE_NAMES, Job, JobStatus
from app.models.tkp_version import TKPVersion
from app.orchestrator import progress
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

MAX_RETRIES = 3
BACKOFF_BASE_SECONDS = 2


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
        result = document_intelligence.run(
            document_intelligence.DocumentIntelligenceInput(str(document.id), document.file_type, content)
        )
        return result.model_dump(mode="json")

    if stage == "classification":
        doc_intel = _load(job, "document_intelligence", DocumentIntelligenceOutput)
        return classification_agent.run(doc_intel).model_dump(mode="json")

    if stage == "knowledge_extraction":
        doc_intel = _load(job, "document_intelligence", DocumentIntelligenceOutput)
        return knowledge_extraction.run(doc_intel).model_dump(mode="json")

    if stage == "teaching_planner":
        cls = _load(job, "classification", ClassificationOutput)
        ek = _load(job, "knowledge_extraction", KnowledgeExtractionOutput)
        return teaching_planner.run(teaching_planner.TeachingPlannerInput(cls, ek)).model_dump(mode="json")

    if stage == "content_generation":
        plan = _load(job, "teaching_planner", TeachingPlanOutput)
        ek = _load(job, "knowledge_extraction", KnowledgeExtractionOutput)
        return content_generator.run(content_generator.ContentGeneratorInput(plan, ek)).model_dump(mode="json")

    if stage == "activity_generation":
        plan = _load(job, "teaching_planner", TeachingPlanOutput)
        ek = _load(job, "knowledge_extraction", KnowledgeExtractionOutput)
        return activity_generator.run(activity_generator.ActivityGeneratorInput(plan, ek)).model_dump(mode="json")

    if stage == "assessment_generation":
        plan = _load(job, "teaching_planner", TeachingPlanOutput)
        ek = _load(job, "knowledge_extraction", KnowledgeExtractionOutput)
        return assessment_generator.run(assessment_generator.AssessmentGeneratorInput(plan, ek)).model_dump(mode="json")

    if stage == "gap_analysis":
        ek = _load(job, "knowledge_extraction", KnowledgeExtractionOutput)
        return gap_analysis.run(ek).model_dump(mode="json")

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


def run_stage(db: Session, job: Job, stage: str, document: Document, storage: StorageBackend) -> None:
    """Execute one stage with retry/backoff, checkpoint the result on success, and
    mark the job failed (explicitly, never silently) on exhaustion."""
    last_exc: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            result = _execute_stage(job, stage, document, storage, db)
            job.stage_results = {**job.stage_results, stage: result}
            completed = sum(1 for s in STAGE_NAMES if s in job.stage_results)
            progress.emit(db, job, stage, int(completed / len(STAGE_NAMES) * 100))
            return
        except Exception as e:  # noqa: BLE001 - any stage failure is retryable, then explicit
            last_exc = e
            if attempt < MAX_RETRIES:
                time.sleep(BACKOFF_BASE_SECONDS * (2 ** (attempt - 1)))

    job.status = JobStatus.FAILED
    job.error = f"Stage '{stage}' failed after {MAX_RETRIES} attempts: {last_exc}"
    db.commit()
    raise StageFailedError(stage, last_exc)


def run_pipeline(db: Session, job: Job) -> None:
    """Drive the job from its current checkpoint to completion, one stage at a
    time. Safe to call repeatedly on the same job: next_stage() always resumes
    from the first uncompleted stage rather than restarting."""
    document = db.get(Document, job.document_id)
    storage = get_storage()

    job.status = JobStatus.RUNNING
    # Stages can arrive pre-checkpointed (document-hash cache reuse on upload),
    # so progress must reflect them even though they never went through
    # run_stage/progress.emit here.
    already_done = sum(1 for s in STAGE_NAMES if s in job.stage_results)
    job.progress_pct = max(job.progress_pct, int(already_done / len(STAGE_NAMES) * 100))
    db.commit()

    stage = next_stage(job)
    while stage is not None:
        job.current_stage = stage
        db.commit()
        run_stage(db, job, stage, document, storage)
        stage = next_stage(job)

    job.status = JobStatus.COMPLETED
    job.progress_pct = 100
    db.commit()
