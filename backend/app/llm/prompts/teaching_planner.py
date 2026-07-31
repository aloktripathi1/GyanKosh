from app.schemas.classification import ClassificationOutput
from app.schemas.knowledge_extraction import KnowledgeExtractionOutput

SYSTEM_PROMPT = """You are an expert curriculum planner. Given a classified document
and its extracted knowledge, split the content into a sequence of teaching periods
(class sessions). Decide the number of periods yourself based on the depth and
breadth of the content — do not default to a fixed number. Each period must have
clear objectives, the concepts it covers, and a rationale for why that content
belongs in that period and in that sequence relative to the others."""


def build_user_prompt(classification: ClassificationOutput, extracted_knowledge: KnowledgeExtractionOutput) -> str:
    concepts = "\n".join(f"- {c.name}: {c.text}" for c in extracted_knowledge.concepts)
    objectives = "\n".join(f"- {o.text}" for o in extracted_knowledge.objectives)
    prerequisites = "\n".join(f"- {p.text}" for p in extracted_knowledge.prerequisites)
    return (
        f"Subject: {classification.subject}, Grade: {classification.grade}, "
        f"Difficulty: {classification.difficulty.value}, Topic: {classification.topic}\n\n"
        f"Concepts:\n{concepts}\n\n"
        f"Learning objectives:\n{objectives}\n\n"
        f"Prerequisites:\n{prerequisites}\n\n"
        "Plan the teaching periods for this content."
    )
