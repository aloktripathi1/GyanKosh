from enum import Enum
from typing import TypeVar

from pydantic import BaseModel

from app.config import get_settings

T = TypeVar("T", bound=BaseModel)


class ModelTier(str, Enum):
    CHEAP = "cheap"  # classification, extraction-to-schema
    STRONG = "strong"  # planning, content, assessment, gap generation


TIER_MODELS = {
    ModelTier.CHEAP: "claude-haiku-4-5-20251001",
    ModelTier.STRONG: "claude-sonnet-5",
}


def structured_call(tier: ModelTier, prompt: str, output_schema: type[T]) -> T:
    """Anthropic wrapper: routes to the model for `tier`, binds the call to
    `output_schema` via tool-use structured output. Implemented in Milestone 2."""
    raise NotImplementedError("LLM client lands in Milestone 2")
