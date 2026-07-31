from app.schemas.document_intelligence import DocumentIntelligenceOutput


class DocumentIntelligenceInput:
    """Placeholder input type until Milestone 2 wires in real parsing (PyMuPDF/python-docx/python-pptx)."""

    def __init__(self, document_id: str, storage_path: str, file_type: str):
        self.document_id = document_id
        self.storage_path = storage_path
        self.file_type = file_type


def run(input: DocumentIntelligenceInput) -> DocumentIntelligenceOutput:
    """Pure function: parse the raw document into structured sections. No side effects
    beyond reading the file via the storage interface. Implemented in Milestone 2."""
    raise NotImplementedError("Document Intelligence agent lands in Milestone 2")
