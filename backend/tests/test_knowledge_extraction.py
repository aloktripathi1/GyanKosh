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
