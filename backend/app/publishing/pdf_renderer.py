import io
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

from app.schemas.tkp import TeacherKnowledgePackage
from app.storage.base import StorageBackend

TEMPLATES_DIR = Path(__file__).parent / "templates"
_env = Environment(loader=FileSystemLoader(TEMPLATES_DIR), autoescape=True)
_BASE_CSS = (TEMPLATES_DIR / "_base.css").read_text()


def _render_to_pdf_bytes(template_name: str, **context) -> bytes:
    html = _env.get_template(template_name).render(base_css=_BASE_CSS, **context)
    return HTML(string=html).write_pdf()


def _save(storage: StorageBackend, job_id: str, filename: str, pdf_bytes: bytes) -> str:
    key = f"tkp/{job_id}/{filename}"
    storage.save(key, io.BytesIO(pdf_bytes))
    return key


def render_lesson_plans(tkp: TeacherKnowledgePackage, storage: StorageBackend) -> str:
    content_by_period = {p.period_number: p for p in tkp.period_content.periods}
    pdf_bytes = _render_to_pdf_bytes(
        "lesson_plans.html",
        classification=tkp.classification,
        teaching_plan=tkp.teaching_plan,
        content_by_period=content_by_period,
    )
    return _save(storage, tkp.job_id, "lesson_plans.pdf", pdf_bytes)


def render_teacher_guide(tkp: TeacherKnowledgePackage, storage: StorageBackend) -> str:
    content_by_period = {p.period_number: p for p in tkp.period_content.periods}
    activities_by_period = {p.period_number: p for p in tkp.activities.periods}
    pdf_bytes = _render_to_pdf_bytes(
        "teacher_guide.html",
        classification=tkp.classification,
        teaching_plan=tkp.teaching_plan,
        extracted_knowledge=tkp.extracted_knowledge,
        content_by_period=content_by_period,
        activities_by_period=activities_by_period,
    )
    return _save(storage, tkp.job_id, "teacher_guide.pdf", pdf_bytes)


def render_assessment_book(tkp: TeacherKnowledgePackage, storage: StorageBackend) -> str:
    pdf_bytes = _render_to_pdf_bytes(
        "assessment_book.html",
        classification=tkp.classification,
        assessments=tkp.assessments,
    )
    return _save(storage, tkp.job_id, "assessment_book.pdf", pdf_bytes)
