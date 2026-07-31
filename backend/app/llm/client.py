from enum import Enum
from functools import lru_cache
from typing import TypeVar

import anthropic
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

MAX_TOKENS = 8192


@lru_cache
def _client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=get_settings().anthropic_api_key)


def structured_call(tier: ModelTier, system_prompt: str, user_prompt: str, output_schema: type[T]) -> T:
    """Route to the model for `tier` and force a tool-use call bound to
    `output_schema`, so the response is schema-valid by construction rather than
    parsed out of free-form prose."""
    tool_name = output_schema.__name__
    response = _client().messages.create(
        model=TIER_MODELS[tier],
        max_tokens=MAX_TOKENS,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
        tools=[
            {
                "name": tool_name,
                "description": f"Return output conforming to the {tool_name} schema.",
                "input_schema": output_schema.model_json_schema(),
            }
        ],
        tool_choice={"type": "tool", "name": tool_name},
    )

    for block in response.content:
        if block.type == "tool_use" and block.name == tool_name:
            return output_schema.model_validate(block.input)

    raise RuntimeError(f"Model did not return a {tool_name} tool_use block")
