"""Document-type hints a user can declare at upload time, used to route
parsing cost-effectively (cheap text extraction vs. OCR fallback), per the
client's cost-aware-routing clarification. Combined with automatic heuristics
in document_intelligence — the hint informs routing, it doesn't override what
the document actually needs."""

MOSTLY_TEXT = "mostly_text"
TEXT_WITH_TABLES = "text_with_tables"
TEXT_WITH_DIAGRAMS = "text_with_diagrams"
TEXT_WITH_EQUATIONS = "text_with_equations"
SCANNED_PDF = "scanned_pdf"
NOT_SURE = "not_sure"

ALL_HINTS = (MOSTLY_TEXT, TEXT_WITH_TABLES, TEXT_WITH_DIAGRAMS, TEXT_WITH_EQUATIONS, SCANNED_PDF, NOT_SURE)
