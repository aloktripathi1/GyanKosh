from app.schemas.knowledge_extraction import KnowledgeExtractionOutput
from app.schemas.teaching_planner import TeachingPlanOutput

SYSTEM_PROMPT = """You are an expert teacher writing classroom-ready lesson materials.
For each period in the teaching plan, produce: an entry ticket, a teacher script,
blackboard notes, a list of activity titles, checkpoint questions with expected
answers, an exit ticket, homework, and a "mentor moment" (a short piece of
practical/motivational guidance for the teacher). Every period, and every
checkpoint question, must cite `grounding_refs`: a list of exact `text` strings
copied verbatim from the extracted knowledge items provided below (objectives,
concepts, definitions, formulae, examples, misconceptions) that the content is
based on. Never invent facts not supported by the extracted knowledge."""


def _format_knowledge(extracted_knowledge: KnowledgeExtractionOutput) -> str:
    lines = []
    for label, items in [
        ("Objectives", extracted_knowledge.objectives),
        ("Concepts", extracted_knowledge.concepts),
        ("Definitions", extracted_knowledge.definitions),
        ("Formulae", extracted_knowledge.formulae),
        ("Examples", extracted_knowledge.examples),
        ("Misconceptions", extracted_knowledge.misconceptions),
    ]:
        lines.append(f"{label}:")
        for item in items:
            lines.append(f'- "{item.text}"')
    return "\n".join(lines)


def build_user_prompt(teaching_plan: TeachingPlanOutput, extracted_knowledge: KnowledgeExtractionOutput) -> str:
    periods = "\n".join(
        f"Period {p.period_number}: {p.title}\n  Objectives: {p.objectives}\n  Concepts: {p.concepts_covered}"
        for p in teaching_plan.periods
    )
    return (
        f"Teaching plan:\n{periods}\n\n"
        f"Extracted knowledge (cite these verbatim in grounding_refs):\n{_format_knowledge(extracted_knowledge)}\n\n"
        "Generate full classroom content for every period listed above."
    )
