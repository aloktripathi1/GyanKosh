from app.schemas.knowledge_extraction import KnowledgeExtractionOutput
from app.schemas.teaching_planner import TeachingPlanOutput

SYSTEM_PROMPT = """You are an expert teacher designing hands-on classroom activities.
For each period in the teaching plan, produce 1-3 activities with a type
(e.g. group work, demonstration, lab, discussion), duration in minutes, required
materials, step-by-step instructions, and success criteria. Every activity must
cite `grounding_refs`: a list of exact `text` strings copied verbatim from the
extracted knowledge items provided below that the activity reinforces. Never
invent facts not supported by the extracted knowledge."""


def _format_knowledge(extracted_knowledge: KnowledgeExtractionOutput) -> str:
    lines = []
    for label, items in [
        ("Concepts", extracted_knowledge.concepts),
        ("Examples", extracted_knowledge.examples),
        ("Applications", extracted_knowledge.applications),
    ]:
        lines.append(f"{label}:")
        for item in items:
            lines.append(f'- "{item.text}"')
    return "\n".join(lines)


def build_user_prompt(teaching_plan: TeachingPlanOutput, extracted_knowledge: KnowledgeExtractionOutput) -> str:
    periods = "\n".join(
        f"Period {p.period_number}: {p.title}\n  Concepts: {p.concepts_covered}" for p in teaching_plan.periods
    )
    return (
        f"Teaching plan:\n{periods}\n\n"
        f"Extracted knowledge (cite these verbatim in grounding_refs):\n{_format_knowledge(extracted_knowledge)}\n\n"
        "Generate classroom activities for every period listed above."
    )
