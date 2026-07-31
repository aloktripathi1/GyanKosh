from pydantic import BaseModel, ValidationError

from app.schemas.validation import SchemaCheckResult


def check(payload: dict, schema: type[BaseModel]) -> SchemaCheckResult:
    try:
        schema.model_validate(payload)
    except ValidationError as e:
        errors = [f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}" for err in e.errors()]
        return SchemaCheckResult(passed=False, errors=errors)
    return SchemaCheckResult(passed=True, errors=[])
