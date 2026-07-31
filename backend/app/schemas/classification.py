from pydantic import BaseModel

from app.schemas.common import DifficultyLevel


class ClassificationOutput(BaseModel):
    subject: str
    grade: str
    difficulty: DifficultyLevel
    topic: str
    chapter: str
    category: str
    language: str
