import pytest

from app.agents.knowledge_extraction import GroundingResolutionError, _resolve_span
from app.schemas.document_intelligence import DocumentIntelligenceOutput, DocumentSection


def _doc():
    return DocumentIntelligenceOutput(
        document_id="d1",
        sections=[DocumentSection(id="s1", level=1, text="Newton's second law states F = m * a exactly.")],
        raw_text="Newton's second law states F = m * a exactly.",
    )


def test_resolve_span_finds_exact_offsets():
    span = _resolve_span(_doc(), "s1", "F = m * a")
    assert span.start_char == 27
    assert span.end_char == 36
    assert span.quote == "F = m * a"


def test_resolve_span_raises_on_unknown_section():
    with pytest.raises(GroundingResolutionError):
        _resolve_span(_doc(), "missing", "F = m * a")


def test_resolve_span_raises_on_nonverbatim_quote():
    with pytest.raises(GroundingResolutionError):
        _resolve_span(_doc(), "s1", "force equals mass times acceleration")


def test_resolve_span_matches_across_a_pdf_line_wrap():
    """Real bug, found running a real NCERT chapter: PyMuPDF inserts a hard
    newline at every visual line wrap, not just paragraph breaks. A model
    quoting a sentence that spans one of these wraps reproduces it with
    normal spacing, not the source's embedded newline — that must still
    resolve, not be treated as fabricated."""
    doc = DocumentIntelligenceOutput(
        document_id="d1",
        sections=[DocumentSection(id="s1", level=1, text="...meant by a\nchemical reaction. How do we know...")],
        raw_text="x",
    )
    span = _resolve_span(doc, "s1", "meant by a chemical reaction")
    assert span.quote == "meant by a\nchemical reaction"
    assert span.start_char == 3
    assert span.end_char == 31


def test_resolve_span_still_rejects_out_of_order_words():
    doc = DocumentIntelligenceOutput(
        document_id="d1",
        sections=[DocumentSection(id="s1", level=1, text="the cat sat on the mat")],
        raw_text="x",
    )
    with pytest.raises(GroundingResolutionError):
        _resolve_span(doc, "s1", "the mat sat on the cat")
