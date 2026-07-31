from pydantic import BaseModel

from app.schemas.validation import SchemaCheckResult


def check(payload: dict, schema: type[BaseModel]) -> SchemaCheckResult:
    """Validate payload against its Pydantic schema. Implemented in Milestone 4."""
    raise NotImplementedError("Schema check lands in Milestone 4")
