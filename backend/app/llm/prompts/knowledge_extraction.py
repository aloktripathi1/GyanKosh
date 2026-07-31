from app.schemas.document_intelligence import DocumentIntelligenceOutput

SYSTEM_PROMPT = """You are an expert curriculum analyst extracting structured knowledge
from a teaching document. Every item you extract MUST include a verbatim quote
copied exactly (character-for-character) from the source section text, and the
id of the section it came from. Never paraphrase inside `quote` — copy the exact
substring. If you cannot find exact supporting text for a claim, do not include it."""


def build_user_prompt(document: DocumentIntelligenceOutput) -> str:
    sections_block = "\n\n".join(
        f"--- section_id: {s.id} ---\n{s.text[:4000]}" for s in document.sections if s.text.strip()
    )
    return (
        f"Document sections:\n\n{sections_block}\n\n"
        "Extract: learning objectives, prerequisites, concepts, definitions, "
        "formulae, keywords, examples, applications, and misconceptions. "
        "For every single item, set `source_section_id` to the section_id it was "
        "found in and `source_quote` to the exact verbatim substring of that "
        "section's text supporting the item."
    )
