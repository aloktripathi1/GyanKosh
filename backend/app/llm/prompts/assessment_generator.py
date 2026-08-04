from app.schemas.knowledge_extraction import KnowledgeExtractionOutput
from app.schemas.teaching_planner import TeachingPlanOutput

SYSTEM_PROMPT = """You are an expert assessment designer. For each period in the
teaching plan, produce MCQs (with options, correct_option_index, and an
explanation), short-answer questions, long-answer questions, and numerical
questions (where the subject matter supports them — leave the list empty
otherwise), each with a model answer/solution and a grading rubric or solution
steps. Every question must cite `grounding_refs`: a list of exact `text` strings
copied verbatim from the extracted knowledge items below that the question
tests. Never invent facts not supported by the extracted knowledge."""


def _format_knowledge(extracted_knowledge: KnowledgeExtractionOutput) -> str:
    lines = []
    for label, items in [
        ("Concepts", extracted_knowledge.concepts),
        ("Definitions", extracted_knowledge.definitions),
        ("Formulae", extracted_knowledge.formulae),
        ("Examples", extracted_knowledge.examples),
    ]:
        lines.append(f"{label}:")
        for item in items:
            lines.append(f'- "{item.text}"')
    return "\n".join(lines)


def build_user_prompt(
    teaching_plan: TeachingPlanOutput, extracted_knowledge: KnowledgeExtractionOutput, language: str = "English"
) -> str:
    periods = "\n".join(
        f"Period {p.period_number}: {p.title}\n  Objectives: {p.objectives}" for p in teaching_plan.periods
    )
    language_line = (
        f"Write every generated field (questions, options, explanations, model answers, rubrics/solution "
        f"steps) in {language}. This applies only to prose you generate — grounding_refs must still be "
        "exact verbatim copies from the extracted knowledge below, in whatever language those quotes are "
        "already in.\n\n"
        if language and language.lower() != "english"
        else ""
    )
    return (
        f"Teaching plan:\n{periods}\n\n"
        f"Extracted knowledge (cite these verbatim in grounding_refs):\n{_format_knowledge(extracted_knowledge)}\n\n"
        f"{language_line}"
        "Generate an assessment for every period listed above."
    )
