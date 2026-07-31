from app.schemas.document_intelligence import DocumentIntelligenceOutput

SYSTEM_PROMPT = """You are an educational content classifier. Given the structured
text of a teaching document, classify it precisely. Base every field only on
evidence in the document; do not guess beyond what the text supports. If the
teacher has provided context (e.g. a grade-level override), prefer it over your
own inference for that field, but never let it override what the document
actually says about subject matter."""


def build_user_prompt(document: DocumentIntelligenceOutput, teaching_context: str | None = None) -> str:
    text = document.raw_text[:12000]
    context_block = f"\nTeacher-provided context: {teaching_context}\n" if teaching_context else ""
    return (
        f"Document title: {document.title or 'unknown'}\n"
        f"{context_block}\n"
        f"Document text:\n{text}\n\n"
        "Classify this document: subject, grade level, difficulty, topic, chapter, "
        "category (e.g. textbook chapter, lecture notes, worksheet), and language."
    )
