from app.schemas.tkp import TeacherKnowledgePackage
from app.storage.base import StorageBackend


def render_lesson_plans(tkp: TeacherKnowledgePackage, storage: StorageBackend) -> str:
    """Render the lesson-plan PDF via HTML/CSS template + WeasyPrint, save through the
    storage interface, return storage_path. Implemented in Milestone 4."""
    raise NotImplementedError("PDF renderer lands in Milestone 4")


def render_teacher_guide(tkp: TeacherKnowledgePackage, storage: StorageBackend) -> str:
    raise NotImplementedError("PDF renderer lands in Milestone 4")


def render_assessment_book(tkp: TeacherKnowledgePackage, storage: StorageBackend) -> str:
    raise NotImplementedError("PDF renderer lands in Milestone 4")
