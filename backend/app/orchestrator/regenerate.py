from sqlalchemy.orm import Session

from app.agents import activity_generator, assessment_generator, classification as classification_agent
from app.agents import content_generator, gap_analysis, knowledge_extraction, teaching_planner
from app.models.job import Job
from app.models.tkp_version import TKPVersion
from app.schemas.activity_generator import ActivityGenerationOutput
from app.schemas.assessment_generator import AssessmentGenerationOutput
from app.schemas.classification import ClassificationOutput
from app.schemas.content_generator import PeriodContentOutput
from app.schemas.document_intelligence import DocumentIntelligenceOutput
from app.schemas.gap_analysis import GapAnalysisOutput
from app.schemas.knowledge_extraction import KnowledgeExtractionOutput
from app.schemas.teaching_planner import TeachingPlanOutput
from app.schemas.validation import ValidationReport
from app.validation import consistency_check, grounding_check, schema_check

REGENERATABLE_SECTIONS = (
    "classification",
    "extracted_knowledge",
    "teaching_plan",
    "period_content",
    "activities",
    "assessments",
    "learning_gaps",
)


class RegenerationError(Exception):
    pass


def _doc_intel(job: Job) -> DocumentIntelligenceOutput:
    if "document_intelligence" not in job.stage_results:
        raise RegenerationError("Original document_intelligence checkpoint is missing for this job")
    return DocumentIntelligenceOutput.model_validate(job.stage_results["document_intelligence"])


def _regenerate_field(section: str, tkp_version: TKPVersion, job: Job) -> dict:
    """Run only the one agent needed for `section`, using the TKP version's
    current fields (not the original job.stage_results) as context — so a
    prior regeneration of an upstream section is reflected."""
    classification = ClassificationOutput.model_validate(tkp_version.classification)
    extracted_knowledge = KnowledgeExtractionOutput.model_validate(tkp_version.extracted_knowledge)
    teaching_plan = TeachingPlanOutput.model_validate(tkp_version.teaching_plan)

    if section == "classification":
        return classification_agent.run(_doc_intel(job)).model_dump(mode="json")
    if section == "extracted_knowledge":
        return knowledge_extraction.run(_doc_intel(job)).model_dump(mode="json")
    if section == "teaching_plan":
        return teaching_planner.run(teaching_planner.TeachingPlannerInput(classification, extracted_knowledge)).model_dump(mode="json")
    if section == "period_content":
        return content_generator.run(content_generator.ContentGeneratorInput(teaching_plan, extracted_knowledge)).model_dump(mode="json")
    if section == "activities":
        return activity_generator.run(activity_generator.ActivityGeneratorInput(teaching_plan, extracted_knowledge)).model_dump(mode="json")
    if section == "assessments":
        return assessment_generator.run(assessment_generator.AssessmentGeneratorInput(teaching_plan, extracted_knowledge)).model_dump(mode="json")
    if section == "learning_gaps":
        return gap_analysis.run(extracted_knowledge).model_dump(mode="json")

    raise RegenerationError(f"Section '{section}' is not regeneratable")


def regenerate_section(db: Session, tkp_version: TKPVersion, section: str) -> TKPVersion:
    if section not in REGENERATABLE_SECTIONS:
        raise RegenerationError(f"Section '{section}' is not regeneratable")

    job = db.get(Job, tkp_version.job_id)
    if job is None:
        raise RegenerationError(f"Parent job {tkp_version.job_id} not found")

    setattr(tkp_version, section, _regenerate_field(section, tkp_version, job))

    validation_report = ValidationReport(
        schema_check=schema_check.check(tkp_version.classification, ClassificationOutput),
        grounding_check=grounding_check.check(
            KnowledgeExtractionOutput.model_validate(tkp_version.extracted_knowledge),
            PeriodContentOutput.model_validate(tkp_version.period_content),
            ActivityGenerationOutput.model_validate(tkp_version.activities),
            AssessmentGenerationOutput.model_validate(tkp_version.assessments),
            GapAnalysisOutput.model_validate(tkp_version.learning_gaps),
        ),
        completeness_check=consistency_check.check_completeness(
            TeachingPlanOutput.model_validate(tkp_version.teaching_plan),
            PeriodContentOutput.model_validate(tkp_version.period_content),
            ActivityGenerationOutput.model_validate(tkp_version.activities),
            AssessmentGenerationOutput.model_validate(tkp_version.assessments),
        ),
        consistency_check=consistency_check.check_consistency(
            TeachingPlanOutput.model_validate(tkp_version.teaching_plan),
            PeriodContentOutput.model_validate(tkp_version.period_content),
            ActivityGenerationOutput.model_validate(tkp_version.activities),
            AssessmentGenerationOutput.model_validate(tkp_version.assessments),
        ),
    )
    tkp_version.validation_report = validation_report.model_dump(mode="json")

    db.commit()
    db.refresh(tkp_version)
    return tkp_version
