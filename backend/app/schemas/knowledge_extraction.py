from pydantic import BaseModel

from app.schemas.common import SourceSpan


class GroundedItem(BaseModel):
    """Base shape for any extracted item: text plus the span it was extracted from."""

    text: str
    source_span: SourceSpan


class Concept(GroundedItem):
    name: str


class Definition(GroundedItem):
    term: str


class Formula(GroundedItem):
    name: str
    expression: str


class Example(GroundedItem):
    related_concept: str | None = None


class Misconception(GroundedItem):
    correction: str


class KnowledgeExtractionOutput(BaseModel):
    objectives: list[GroundedItem]
    prerequisites: list[GroundedItem]
    concepts: list[Concept]
    definitions: list[Definition]
    formulae: list[Formula]
    keywords: list[GroundedItem]
    examples: list[Example]
    applications: list[GroundedItem]
    misconceptions: list[Misconception]
