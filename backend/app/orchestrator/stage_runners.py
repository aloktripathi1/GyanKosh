"""Shared 'given typed inputs, call agent X and return its dict' functions.

Both the sequential pipeline (pipeline.py) and single-section regeneration
(regenerate.py) need to invoke the same agents the same way — they only
differ in *where* the input Pydantic objects come from (job.stage_results
for the pipeline, the current TKPVersion fields for regeneration). Without
this module, that construction logic was duplicated in two independent
dispatch tables, which drift out of sync whenever an agent's input contract
changes — a change to one is easy to forget to make in the other.
"""

from app.agents import activity_generator, assessment_generator
from app.agents import classification as classification_agent
from app.agents import content_generator, gap_analysis, knowledge_extraction, teaching_planner
from app.schemas.classification import ClassificationOutput
from app.schemas.document_intelligence import DocumentIntelligenceOutput
from app.schemas.knowledge_extraction import KnowledgeExtractionOutput
from app.schemas.teaching_planner import TeachingPlanOutput


def run_classification(doc_intel: DocumentIntelligenceOutput, teaching_context: str | None) -> dict:
    return classification_agent.run(doc_intel, teaching_context).model_dump(mode="json")


def run_knowledge_extraction(doc_intel: DocumentIntelligenceOutput) -> dict:
    return knowledge_extraction.run(doc_intel).model_dump(mode="json")


def run_teaching_planner(cls: ClassificationOutput, ek: KnowledgeExtractionOutput, teaching_context: str | None) -> dict:
    planner_input = teaching_planner.TeachingPlannerInput(cls, ek, teaching_context)
    return teaching_planner.run(planner_input).model_dump(mode="json")


def run_content_generation(plan: TeachingPlanOutput, ek: KnowledgeExtractionOutput) -> dict:
    return content_generator.run(content_generator.ContentGeneratorInput(plan, ek)).model_dump(mode="json")


def run_activity_generation(plan: TeachingPlanOutput, ek: KnowledgeExtractionOutput) -> dict:
    return activity_generator.run(activity_generator.ActivityGeneratorInput(plan, ek)).model_dump(mode="json")


def run_assessment_generation(plan: TeachingPlanOutput, ek: KnowledgeExtractionOutput) -> dict:
    return assessment_generator.run(assessment_generator.AssessmentGeneratorInput(plan, ek)).model_dump(mode="json")


def run_gap_analysis(ek: KnowledgeExtractionOutput) -> dict:
    return gap_analysis.run(ek).model_dump(mode="json")
