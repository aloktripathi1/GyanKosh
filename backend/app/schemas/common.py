from enum import Enum

from pydantic import BaseModel, Field


class SourceSpan(BaseModel):
    """Pointer back into the Stage-1 structured document. Required on every
    Stage-3 extracted item so Stage-9 grounding checks have something to verify against."""

    section_id: str = Field(description="id of the section/heading in the Stage 1 structured document")
    page: int | None = Field(default=None, description="page number in the original document, if applicable")
    start_char: int = Field(description="character offset of the span start within the section text")
    end_char: int = Field(description="character offset of the span end within the section text")
    quote: str = Field(description="verbatim text of the source span, for human-auditable grounding")


class DifficultyLevel(str, Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class SeverityLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
