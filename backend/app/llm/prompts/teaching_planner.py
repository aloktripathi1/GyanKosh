from app.schemas.classification import ClassificationOutput
from app.schemas.knowledge_extraction import KnowledgeExtractionOutput

SYSTEM_PROMPT = """You are an expert curriculum planner. Given a classified document
and its extracted knowledge, split the content into a sequence of teaching periods
(class sessions). Decide the number of periods yourself based on the depth and
breadth of the content — do not default to a fixed number, and do not default to a
fixed period length. Each period must have clear objectives, the concepts it covers,
a rationale for why that content belongs in that period and in that sequence relative
to the others, and a recommended_duration_minutes that reflects how long this
specific content actually takes to teach well at this grade level — a short
conceptual period might realistically need 20-30 minutes, a dense numerical-practice
period might need 50-60. Base the estimate on content volume and grade level, not a
generic classroom-period default."""


def build_user_prompt(
    classification: ClassificationOutput,
    extracted_knowledge: KnowledgeExtractionOutput,
    teaching_context: str | None = None,
) -> str:
    concepts = "\n".join(f"- {c.name}: {c.text}" for c in extracted_knowledge.concepts)
    objectives = "\n".join(f"- {o.text}" for o in extracted_knowledge.objectives)
    prerequisites = "\n".join(f"- {p.text}" for p in extracted_knowledge.prerequisites)
    context_block = f"\nTeacher-provided context (use this to shape pacing and objectives): {teaching_context}\n" if teaching_context else ""
    return (
        f"Subject: {classification.subject}, Grade: {classification.grade}, "
        f"Difficulty: {classification.difficulty.value}, Topic: {classification.topic}\n"
        f"{context_block}\n"
        f"Concepts:\n{concepts}\n\n"
        f"Learning objectives:\n{objectives}\n\n"
        f"Prerequisites:\n{prerequisites}\n\n"
        "Plan the teaching periods for this content."
    )
