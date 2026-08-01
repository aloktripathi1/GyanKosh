"""Orchestrator resilience tests. The retry/checkpoint/resume algorithm in
app.orchestrator.pipeline is DB-agnostic (it only calls job.stage_results,
job.status, db.commit()), so these tests use a lightweight fake Session/Job
instead of a live Postgres connection, matching Section 14's "mock the LLM
client" philosophy applied to the DB boundary instead."""

import uuid

import pytest

from app.models.job import STAGE_NAMES, JobStatus
from app.orchestrator import pipeline, stage_runners
from app.schemas.activity_generator import ActivityGenerationOutput
from app.schemas.assessment_generator import AssessmentGenerationOutput
from app.schemas.classification import ClassificationOutput, DifficultyLevel
from app.schemas.common import SourceSpan
from app.schemas.content_generator import PeriodContentOutput
from app.schemas.document_intelligence import DocumentIntelligenceOutput, DocumentSection
from app.schemas.gap_analysis import GapAnalysisOutput
from app.schemas.knowledge_extraction import Concept, GroundedItem, KnowledgeExtractionOutput
from app.schemas.teaching_planner import Period, TeachingPlanOutput

SPAN = SourceSpan(section_id="s1", start_char=0, end_char=5, quote="F=ma.")


class FakeJob:
    def __init__(self, stage_results=None):
        self.id = uuid.uuid4()
        self.document_id = uuid.uuid4()
        self.status = JobStatus.PENDING
        self.current_stage = None
        self.progress_pct = 0
        self.error = None
        self.teaching_context = None
        self.stage_results = stage_results or {}
        self.stage_timings = {}


class FakeDocument:
    def __init__(self, storage_path: str):
        self.id = uuid.uuid4()
        self.file_type = "txt"
        self.storage_path = storage_path
        self.document_type_hint = None


class FakeSession:
    """Only implements what run_pipeline/run_stage/_run_publishing touch."""

    def __init__(self, document):
        self._document = document
        self.added = []

    def get(self, model, id_):
        return self._document

    def commit(self):
        pass

    def add(self, obj):
        self.added.append(obj)

    def flush(self):
        pass


@pytest.fixture
def stub_agents(monkeypatch):
    """Replace every agent's .run with a fast, deterministic stub returning a
    minimal valid output for its stage."""
    doc_intel = DocumentIntelligenceOutput(
        document_id="d1", sections=[DocumentSection(id="s1", level=1, text="Newton's second law: F=ma.")], raw_text="x"
    )
    classification = ClassificationOutput(
        subject="Physics", grade="9", difficulty=DifficultyLevel.BEGINNER, topic="t", chapter="c", category="cat", language="en"
    )
    extraction = KnowledgeExtractionOutput(
        objectives=[GroundedItem(text="o", source_span=SPAN)],
        prerequisites=[], concepts=[Concept(text="F=ma.", name="N2", source_span=SPAN)],
        definitions=[], formulae=[], keywords=[], examples=[], applications=[], misconceptions=[],
    )
    plan = TeachingPlanOutput(
        periods=[Period(period_number=1, title="P1", objectives=["o"], concepts_covered=["c"], sequencing_rationale="r", recommended_duration_minutes=40)],
        total_periods=1, planning_rationale="r",
    )
    content = PeriodContentOutput(periods=[])
    activities = ActivityGenerationOutput(periods=[])
    assessments = AssessmentGenerationOutput(periods=[])
    gaps = GapAnalysisOutput(gaps=[])

    calls = {name: 0 for name in STAGE_NAMES}

    def make_stub(name, value):
        def stub(*args, **kwargs):
            calls[name] += 1
            return value
        return stub

    monkeypatch.setattr(pipeline.document_intelligence, "run", make_stub("document_intelligence", doc_intel))
    monkeypatch.setattr(stage_runners.classification_agent, "run", make_stub("classification", classification))
    monkeypatch.setattr(stage_runners.knowledge_extraction, "run", make_stub("knowledge_extraction", extraction))
    monkeypatch.setattr(stage_runners.teaching_planner, "run", make_stub("teaching_planner", plan))
    monkeypatch.setattr(stage_runners.content_generator, "run", make_stub("content_generation", content))
    monkeypatch.setattr(stage_runners.activity_generator, "run", make_stub("activity_generation", activities))
    monkeypatch.setattr(stage_runners.assessment_generator, "run", make_stub("assessment_generation", assessments))
    monkeypatch.setattr(stage_runners.gap_analysis, "run", make_stub("gap_analysis", gaps))
    monkeypatch.setattr(pipeline, "render_lesson_plans", lambda tkp, storage: "tkp/lesson_plans.pdf")
    monkeypatch.setattr(pipeline, "render_teacher_guide", lambda tkp, storage: "tkp/teacher_guide.pdf")
    monkeypatch.setattr(pipeline, "render_assessment_book", lambda tkp, storage: "tkp/assessment_book.pdf")

    return calls


def test_full_pipeline_completes_and_checkpoints_every_stage(stub_agents, storage):
    document = FakeDocument("doc.txt")
    db = FakeSession(document)
    job = FakeJob()

    pipeline.run_pipeline(db, job)

    assert job.status == JobStatus.COMPLETED
    assert job.progress_pct == 100
    assert set(job.stage_results.keys()) == set(STAGE_NAMES)
    agent_backed_stages = [s for s in STAGE_NAMES if s not in ("validation", "publishing")]
    assert all(stub_agents[s] == 1 for s in agent_backed_stages)
    assert len(db.added) == 1  # the TKPVersion row

    # Observability: every stage records a wall-clock duration, not just its
    # output — this is what a per-job timing breakdown reads from.
    assert set(job.stage_timings.keys()) == set(STAGE_NAMES)
    assert all(isinstance(v, float) and v >= 0 for v in job.stage_timings.values())


def test_progress_reflects_precached_stages_from_document_hash_reuse(stub_agents, storage):
    """A re-upload of an already-seen document pre-seeds document_intelligence/
    classification/knowledge_extraction into stage_results at job creation
    (see api/documents.py's cache reuse). Progress must reflect that seeded
    work immediately, not read 0% while the stepper shows those stages done."""
    document = FakeDocument("doc.txt")
    db = FakeSession(document)
    doc_intel = DocumentIntelligenceOutput(
        document_id="d1", sections=[DocumentSection(id="s1", level=1, text="Newton's second law: F=ma.")], raw_text="x"
    )
    classification = ClassificationOutput(
        subject="Physics", grade="9", difficulty=DifficultyLevel.BEGINNER, topic="t", chapter="c", category="cat", language="en"
    )
    extraction = KnowledgeExtractionOutput(
        objectives=[GroundedItem(text="o", source_span=SPAN)],
        prerequisites=[], concepts=[Concept(text="F=ma.", name="N2", source_span=SPAN)],
        definitions=[], formulae=[], keywords=[], examples=[], applications=[], misconceptions=[],
    )
    job = FakeJob(
        stage_results={
            "document_intelligence": doc_intel.model_dump(mode="json"),
            "classification": classification.model_dump(mode="json"),
            "knowledge_extraction": extraction.model_dump(mode="json"),
        }
    )

    progress_at_first_new_stage = {}
    real_teaching_planner_run = stage_runners.teaching_planner.run

    def capture_progress(*args, **kwargs):
        progress_at_first_new_stage["value"] = job.progress_pct
        return real_teaching_planner_run(*args, **kwargs)

    stage_runners.teaching_planner.run = capture_progress
    try:
        pipeline.run_pipeline(db, job)
    finally:
        stage_runners.teaching_planner.run = real_teaching_planner_run

    # 3 of 10 stages were already checkpointed before the pipeline even started.
    assert progress_at_first_new_stage["value"] == 30

    assert job.status == JobStatus.COMPLETED
    # The pre-cached stages' agents must never be re-invoked.
    assert stub_agents["document_intelligence"] == 0
    assert stub_agents["classification"] == 0
    assert stub_agents["knowledge_extraction"] == 0
def test_resume_from_checkpoint_skips_completed_stages_and_no_duplicate_calls(stub_agents, storage):
    """Definition of Done: pipeline survives a mid-run 'worker kill' and resumes
    from the last checkpointed stage instead of restarting, with no duplicate
    LLM calls for already-completed stages."""
    document = FakeDocument("doc.txt")
    db = FakeSession(document)

    # Simulate a job that already checkpointed the first 3 stages before the
    # worker died — as if run_pipeline had been interrupted mid-run.
    precomputed = {}
    for stage in STAGE_NAMES[:3]:
        precomputed[stage] = {"__stub__": stage}  # stand-in checkpoint payloads

    # _execute_stage would try to parse these with the real schema for later
    # stages, so instead precompute via a real (short) run up to stage 3, then
    # kill it, to get valid checkpoint payloads.
    job = FakeJob()
    original_execute = pipeline._execute_stage
    call_count = {"n": 0}

    def killer(job, stage, document, storage, db):
        call_count["n"] += 1
        if call_count["n"] > 3:
            raise RuntimeError("simulated worker kill")
        return original_execute(job, stage, document, storage, db)

    import app.orchestrator.pipeline as pipeline_module

    pipeline_module._execute_stage = killer
    try:
        with pytest.raises(pipeline.StageFailedError):
            pipeline.run_pipeline(db, job)
    finally:
        pipeline_module._execute_stage = original_execute

    assert job.status == JobStatus.FAILED
    completed_after_kill = set(job.stage_results.keys())
    assert completed_after_kill == set(STAGE_NAMES[:3])
    calls_before_resume = dict(stub_agents)

    # "Restart the worker": call run_pipeline again on the same job. It must
    # resume from stage 4, not redo stages 1-3.
    job.status = JobStatus.PENDING
    job.error = None
    pipeline.run_pipeline(db, job)

    assert job.status == JobStatus.COMPLETED
    assert set(job.stage_results.keys()) == set(STAGE_NAMES)
    for stage in STAGE_NAMES[:3]:
        assert calls_before_resume[stage] == stub_agents[stage], f"{stage} was re-invoked after resume"


def test_pipeline_completes_for_non_english_content(stub_agents, storage):
    """Section 15: nothing in the orchestrator/validation path may assume
    English content — a non-English `language` classification must flow
    through to a normal completed run, not a special-cased failure."""
    document = FakeDocument("doc.txt")
    db = FakeSession(document)
    job = FakeJob()

    hindi_classification = ClassificationOutput(
        subject="विज्ञान", grade="9", difficulty=DifficultyLevel.BEGINNER, topic="t", chapter="c", category="cat", language="hi"
    )
    real_run = stage_runners.classification_agent.run
    stage_runners.classification_agent.run = lambda *a, **k: hindi_classification
    try:
        pipeline.run_pipeline(db, job)
    finally:
        stage_runners.classification_agent.run = real_run

    assert job.status == JobStatus.COMPLETED
    assert job.stage_results["classification"]["language"] == "hi"


def test_pipeline_completes_with_thin_extraction_and_single_period(stub_agents, storage):
    """Section 15: a document too thin to justify more than one period, with
    minimal extracted knowledge, must still complete cleanly — not assume a
    'typical' multi-concept document."""
    document = FakeDocument("doc.txt")
    db = FakeSession(document)
    job = FakeJob()

    thin_extraction = KnowledgeExtractionOutput(
        objectives=[GroundedItem(text="o", source_span=SPAN)],
        prerequisites=[], concepts=[], definitions=[], formulae=[], keywords=[],
        examples=[], applications=[], misconceptions=[],
    )
    real_run = stage_runners.knowledge_extraction.run
    stage_runners.knowledge_extraction.run = lambda *a, **k: thin_extraction
    try:
        pipeline.run_pipeline(db, job)
    finally:
        stage_runners.knowledge_extraction.run = real_run

    assert job.status == JobStatus.COMPLETED
    assert job.stage_results["knowledge_extraction"]["concepts"] == []
    assert len(job.stage_results["knowledge_extraction"]["objectives"]) == 1


def test_pipeline_completes_with_ambiguous_multi_subject_classification(stub_agents, storage):
    document = FakeDocument("doc.txt")
    db = FakeSession(document)
    job = FakeJob()

    ambiguous = ClassificationOutput(
        subject="Interdisciplinary (Science & Social Science)", grade="9",
        difficulty=DifficultyLevel.INTERMEDIATE, topic="t", chapter="c", category="cat", language="en",
    )
    real_run = stage_runners.classification_agent.run
    stage_runners.classification_agent.run = lambda *a, **k: ambiguous
    try:
        pipeline.run_pipeline(db, job)
    finally:
        stage_runners.classification_agent.run = real_run

    assert job.status == JobStatus.COMPLETED
    assert job.stage_results["classification"]["subject"] == "Interdisciplinary (Science & Social Science)"


def test_stage_retries_then_succeeds(stub_agents, storage):
    document = FakeDocument("doc.txt")
    db = FakeSession(document)
    job = FakeJob()

    attempts = {"n": 0}
    real_run = stage_runners.classification_agent.run

    def flaky(*args, **kwargs):
        attempts["n"] += 1
        if attempts["n"] < 2:
            raise RuntimeError("transient LLM error")
        return real_run(*args, **kwargs)

    job.stage_results["document_intelligence"] = pipeline.document_intelligence.run(None).model_dump(mode="json")
    stage_runners.classification_agent.run = flaky
    try:
        pipeline.run_stage(db, job, "classification", document, storage)
    finally:
        stage_runners.classification_agent.run = real_run

    assert attempts["n"] == 2
    assert "classification" in job.stage_results
    assert job.status != JobStatus.FAILED


def test_stage_fails_explicitly_after_exhausting_retries(stub_agents, storage):
    document = FakeDocument("doc.txt")
    db = FakeSession(document)
    job = FakeJob()
    job.stage_results["document_intelligence"] = pipeline.document_intelligence.run(None).model_dump(mode="json")

    real_run = stage_runners.classification_agent.run

    def always_fails(*args, **kwargs):
        raise RuntimeError("permanent LLM error")

    stage_runners.classification_agent.run = always_fails
    try:
        with pytest.raises(pipeline.StageFailedError):
            pipeline.run_stage(db, job, "classification", document, storage)
    finally:
        stage_runners.classification_agent.run = real_run

    assert job.status == JobStatus.FAILED
    assert job.error is not None
    assert "classification" in job.error
