from app.schemas.document_intelligence import DocumentIntelligenceOutput

SYSTEM_PROMPT = """You are an educational content classifier. Given the structured
text of a teaching document, classify it precisely. Base every field only on
evidence in the document; do not guess beyond what the text supports."""


def build_user_prompt(document: DocumentIntelligenceOutput) -> str:
    text = document.raw_text[:12000]
    return (
        f"Document title: {document.title or 'unknown'}\n\n"
        f"Document text:\n{text}\n\n"
        "Classify this document: subject, grade level, difficulty, topic, chapter, "
        "category (e.g. textbook chapter, lecture notes, worksheet), and language."
    )
