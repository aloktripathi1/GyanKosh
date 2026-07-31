import base64
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

MAX_TOKENS = 32000


@lru_cache
def _client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=get_settings().anthropic_api_key)


def structured_call(tier: ModelTier, system_prompt: str, user_prompt: str, output_schema: type[T]) -> T:
    """Route to the model for `tier` and force a tool-use call bound to
    `output_schema`, so the response is schema-valid by construction rather than
    parsed out of free-form prose.

    The system prompt and tool definition are identical across every call to a
    given stage (they don't depend on document content) and are marked cacheable:
    Anthropic caches everything up to and including the marked block — tool
    definitions, then system — so a cache hit covers both. This pays off on
    same-stage retries (identical prompt, per the orchestrator's retry-on-failure
    path) and across different jobs/documents hitting the same stage within the
    5-minute cache window, at ~10% of the input-token cost on a hit."""
    tool_name = output_schema.__name__
    response = _client().messages.create(
        model=TIER_MODELS[tier],
        max_tokens=MAX_TOKENS,
        system=[{"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}],
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

    if response.stop_reason == "max_tokens":
        raise RuntimeError(
            f"Response truncated at max_tokens ({MAX_TOKENS}) before completing {tool_name} — "
            "the document is likely too dense for a single call at this stage."
        )

    for block in response.content:
        if block.type == "tool_use" and block.name == tool_name:
            return output_schema.model_validate(block.input)

    raise RuntimeError(f"Model did not return a {tool_name} tool_use block")


OCR_SYSTEM_PROMPT = """You transcribe scanned textbook pages into clean text.
Reproduce every word exactly as written — do not summarize, paraphrase, or skip
content. Preserve structure: headings on their own line, tables as markdown
tables, equations as LaTeX between $ delimiters, figure/activity captions
included as plain text. If the page is blank or contains no legible text,
respond with exactly: [blank page]"""


def ocr_page_text(image_bytes: bytes, media_type: str = "image/png") -> str:
    """Vision fallback for pages a text-layer extractor can't read (scanned
    PDFs, image-only pages) — only called when the cheap path already failed,
    per the cost-aware routing the document-type hint exists to support."""
    response = _client().messages.create(
        model=TIER_MODELS[ModelTier.STRONG],
        max_tokens=MAX_TOKENS,
        system=[{"type": "text", "text": OCR_SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": media_type, "data": base64.b64encode(image_bytes).decode()},
                    },
                    {"type": "text", "text": "Transcribe this page."},
                ],
            }
        ],
    )
    return "".join(block.text for block in response.content if block.type == "text").strip()
