from app.schemas.knowledge_extraction import KnowledgeExtractionOutput

SYSTEM_PROMPT = """You are an expert in diagnosing student learning gaps. Given a
document's extracted misconceptions and concepts, produce a learning-gap report:
for each misconception, assess its severity (low/medium/high), write 1-3
diagnostic questions that would reveal whether a student holds it, and a
remediation strategy. Every gap and diagnostic question must cite
`grounding_refs`: a list of exact `text` strings copied verbatim from the
extracted knowledge items provided below. Never invent facts not supported by
the extracted knowledge."""


def _format_knowledge(extracted_knowledge: KnowledgeExtractionOutput) -> str:
    lines = ["Misconceptions:"]
    for item in extracted_knowledge.misconceptions:
        lines.append(f'- "{item.text}" (correction: {item.correction})')
    lines.append("Concepts:")
    for item in extracted_knowledge.concepts:
        lines.append(f'- "{item.text}"')
    return "\n".join(lines)


def build_user_prompt(extracted_knowledge: KnowledgeExtractionOutput) -> str:
    return (
        f"Extracted knowledge (cite these verbatim in grounding_refs):\n{_format_knowledge(extracted_knowledge)}\n\n"
        "Produce the learning-gap analysis."
    )
