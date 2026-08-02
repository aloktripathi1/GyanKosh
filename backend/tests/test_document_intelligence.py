"""Tests for the OCR fallback path: pages with little/no extractable text
(scans, image-only pages) should be routed to vision-based transcription
instead of silently degrading to near-empty text."""

from pathlib import Path

import fitz
import pytest

from app.agents import document_intelligence
from app.agents.document_type_hints import SCANNED_PDF

# Real, non-mocked source files uploaded through the live pipeline this
# session (docx: NCERT-style Physics Electricity chapter, pptx: a Physics
# Motion in a Straight Line lecture deck) — not synthetic fixtures, the
# actual documents used to generate the /samples entries.
_SAMPLES_INPUT = Path(__file__).resolve().parents[2] / "samples" / "input"
_REAL_DOCX = _SAMPLES_INPUT / "class10_physics_ch11_electricty.docx"
_REAL_PPTX = _SAMPLES_INPUT / "class11_physics_ch2.pptx"


def _blank_pdf_bytes() -> bytes:
    doc = fitz.open()
    doc.new_page()  # no text inserted — an empty text layer, like a scanned page
    return doc.tobytes()


def _text_pdf_bytes(text: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    return doc.tobytes()


def test_low_text_page_falls_back_to_ocr(monkeypatch):
    calls = []

    def fake_ocr(image_bytes, media_type="image/png"):
        calls.append(image_bytes)
        return "Transcribed page content from vision OCR."

    monkeypatch.setattr(document_intelligence, "ocr_page_text", fake_ocr)

    result = document_intelligence.run(
        document_intelligence.DocumentIntelligenceInput("d1", "pdf", _blank_pdf_bytes())
    )

    assert len(calls) == 1
    assert result.sections[0].text == "Transcribed page content from vision OCR."


def test_normal_text_page_never_calls_ocr(monkeypatch):
    def fail_if_called(*args, **kwargs):
        raise AssertionError("OCR should not be called for a page with real extractable text")

    monkeypatch.setattr(document_intelligence, "ocr_page_text", fail_if_called)

    text = "This page has plenty of real, extractable text content well above the threshold. " * 3
    result = document_intelligence.run(
        document_intelligence.DocumentIntelligenceInput("d1", "pdf", _text_pdf_bytes(text))
    )

    assert "real, extractable text" in result.sections[0].text


def test_corrupted_pdf_raises_clear_error(monkeypatch):
    with pytest.raises(ValueError, match="corrupted"):
        document_intelligence.run(
            document_intelligence.DocumentIntelligenceInput("d1", "pdf", b"this is not a pdf file at all")
        )


def test_zero_page_pdf_raises_clear_error(monkeypatch):
    class _FakeDoc:
        page_count = 0
        metadata = {}

    monkeypatch.setattr(fitz, "open", lambda **kwargs: _FakeDoc())

    with pytest.raises(ValueError, match="no pages"):
        document_intelligence.run(document_intelligence.DocumentIntelligenceInput("d1", "pdf", b"%PDF-fake"))


def test_oversized_pdf_is_rejected_before_processing_any_page(monkeypatch):
    class _FakeDoc:
        page_count = document_intelligence.MAX_PDF_PAGES + 1
        metadata = {}

        def __iter__(self):
            raise AssertionError("must reject before iterating pages")

    monkeypatch.setattr(fitz, "open", lambda **kwargs: _FakeDoc())

    with pytest.raises(ValueError, match="exceeding"):
        document_intelligence.run(document_intelligence.DocumentIntelligenceInput("d1", "pdf", b"%PDF-fake"))


def test_blank_page_with_no_ocr_recovery_raises_clear_error(monkeypatch):
    """A scanned page that OCR also can't read (truly blank) must be flagged
    explicitly rather than silently producing an empty TKP downstream."""
    monkeypatch.setattr(document_intelligence, "ocr_page_text", lambda *a, **k: "[blank page]")

    with pytest.raises(ValueError, match="No extractable text"):
        document_intelligence.run(
            document_intelligence.DocumentIntelligenceInput("d1", "pdf", _blank_pdf_bytes())
        )


def test_empty_txt_raises_clear_error():
    with pytest.raises(ValueError, match="No extractable text"):
        document_intelligence.run(document_intelligence.DocumentIntelligenceInput("d1", "txt", b"   \n\n  "))


def test_scanned_hint_lowers_the_bar_for_ocr(monkeypatch):
    """A short-but-nonzero text layer (e.g. a watermark) still gets OCR'd when
    the user declares the document is scanned."""
    calls = []

    def fake_ocr(image_bytes, media_type="image/png"):
        calls.append(image_bytes)
        return "Full transcription via OCR."

    monkeypatch.setattr(document_intelligence, "ocr_page_text", fake_ocr)

    # 100 chars: above the un-hinted 40-char threshold (wouldn't trigger OCR on
    # its own) but below the 200-char threshold a "scanned" hint applies.
    short_text = "Stray watermark or header text extracted from an otherwise-scanned page. " * 1
    result = document_intelligence.run(
        document_intelligence.DocumentIntelligenceInput("d1", "pdf", _text_pdf_bytes(short_text), SCANNED_PDF)
    )

    assert len(calls) == 1
    assert result.sections[0].text == "Full transcription via OCR."


# --- DOCX/PPTX, using the real uploaded files, not mocks or synthetic fixtures ---


@pytest.mark.skipif(not _REAL_DOCX.exists(), reason=f"real sample file not present: {_REAL_DOCX}")
def test_docx_parses_real_file_without_crashing():
    content = _REAL_DOCX.read_bytes()
    result = document_intelligence.run(document_intelligence.DocumentIntelligenceInput("d1", "docx", content))

    assert result.sections
    assert result.raw_text.strip()


@pytest.mark.skipif(not _REAL_DOCX.exists(), reason=f"real sample file not present: {_REAL_DOCX}")
def test_docx_preserves_headings_as_distinct_sections():
    content = _REAL_DOCX.read_bytes()
    result = document_intelligence.run(document_intelligence.DocumentIntelligenceInput("d1", "docx", content))

    headed_sections = [s for s in result.sections if s.heading]
    assert headed_sections, "expected at least one section with a heading detected, not everything flattened into one blob"


@pytest.mark.skipif(not _REAL_DOCX.exists(), reason=f"real sample file not present: {_REAL_DOCX}")
def test_docx_extracts_real_electricity_content_not_garbage():
    """Confirms _parse_docx actually ran against real content, not a
    fallback or an empty/garbage extraction — this is the same chapter
    verified live via the pipeline (samples/physics_electricity.json),
    so the vocabulary must be genuinely present."""
    content = _REAL_DOCX.read_bytes()
    result = document_intelligence.run(document_intelligence.DocumentIntelligenceInput("d1", "docx", content))

    lowered = result.raw_text.lower()
    assert "resistance" in lowered or "current" in lowered or "circuit" in lowered


@pytest.mark.skipif(not _REAL_PPTX.exists(), reason=f"real sample file not present: {_REAL_PPTX}")
def test_pptx_parses_real_file_without_crashing():
    content = _REAL_PPTX.read_bytes()
    result = document_intelligence.run(document_intelligence.DocumentIntelligenceInput("d1", "pptx", content))

    assert result.sections
    assert result.raw_text.strip()


@pytest.mark.skipif(not _REAL_PPTX.exists(), reason=f"real sample file not present: {_REAL_PPTX}")
def test_pptx_preserves_slide_titles_as_headings():
    content = _REAL_PPTX.read_bytes()
    result = document_intelligence.run(document_intelligence.DocumentIntelligenceInput("d1", "pptx", content))

    headed_sections = [s for s in result.sections if s.heading]
    assert headed_sections, "expected at least one slide title detected as a heading, not everything flattened into one blob"


@pytest.mark.skipif(not _REAL_PPTX.exists(), reason=f"real sample file not present: {_REAL_PPTX}")
def test_pptx_infers_title_slide_heading_when_no_placeholder_exists():
    """Regression test for a real bug: this deck was converted from a PDF, so
    no slide uses an actual title placeholder and shape == slide.shapes.title
    was always False, leaving every heading None. The fix infers a heading
    only for the first slide (a title slide is a safe, narrow assumption) and
    deliberately does NOT try to guess headings on dense content slides,
    where the real deck's largest-font text is just a mid-equation fragment,
    not a heading — a wrong heading is worse than none."""
    content = _REAL_PPTX.read_bytes()
    result = document_intelligence.run(document_intelligence.DocumentIntelligenceInput("d1", "pptx", content))

    assert result.sections[0].heading == "Chapter Two"
    # content-heavy slides (index 1+) must not get a fabricated heading
    assert all(s.heading is None for s in result.sections[1:])


@pytest.mark.skipif(not _REAL_PPTX.exists(), reason=f"real sample file not present: {_REAL_PPTX}")
def test_pptx_extracts_real_motion_content_not_garbage():
    """Confirms _parse_pptx actually ran against real content — same deck
    verified live via the pipeline (classification came back 'Motion in a
    Straight Line'), so that vocabulary must be genuinely present."""
    content = _REAL_PPTX.read_bytes()
    result = document_intelligence.run(document_intelligence.DocumentIntelligenceInput("d1", "pptx", content))

    lowered = result.raw_text.lower()
    assert "motion" in lowered or "velocity" in lowered or "displacement" in lowered
