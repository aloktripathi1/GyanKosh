"""Tests for the OCR fallback path: pages with little/no extractable text
(scans, image-only pages) should be routed to vision-based transcription
instead of silently degrading to near-empty text."""

import fitz
import pytest

from app.agents import document_intelligence
from app.agents.document_type_hints import SCANNED_PDF


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
