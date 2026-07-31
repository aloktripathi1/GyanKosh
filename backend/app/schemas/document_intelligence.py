from pydantic import BaseModel, Field


class TableBlock(BaseModel):
    id: str
    caption: str | None = None
    rows: list[list[str]]
    page: int | None = None


class FigureBlock(BaseModel):
    id: str
    caption: str | None = None
    page: int | None = None
    description: str | None = Field(default=None, description="alt-text / extracted description of the figure")


class EquationBlock(BaseModel):
    id: str
    latex: str | None = None
    raw_text: str
    page: int | None = None


class DocumentSection(BaseModel):
    id: str
    heading: str | None = None
    level: int = Field(description="heading depth, 1 = top-level")
    text: str
    page: int | None = None
    tables: list[TableBlock] = Field(default_factory=list)
    figures: list[FigureBlock] = Field(default_factory=list)
    equations: list[EquationBlock] = Field(default_factory=list)


class DocumentIntelligenceOutput(BaseModel):
    document_id: str
    title: str | None = None
    sections: list[DocumentSection]
    page_count: int | None = None
    raw_text: str = Field(description="full concatenated text, used as fallback context")
