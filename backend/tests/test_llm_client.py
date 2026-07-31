"""Tests for the low-level Anthropic wrapper itself (not the agents that call
it) — prompt-cache wiring and truncation handling live here since every agent
goes through this one chokepoint."""

from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from app.llm import client as llm_client


class _Output(BaseModel):
    value: str


class _FakeMessages:
    def __init__(self, response):
        self._response = response
        self.last_call_kwargs = None

    def create(self, **kwargs):
        self.last_call_kwargs = kwargs
        return self._response


class _FakeAnthropicClient:
    def __init__(self, response):
        self.messages = _FakeMessages(response)


def _tool_use_response(tool_name: str, input_data: dict, stop_reason: str = "tool_use"):
    return SimpleNamespace(
        stop_reason=stop_reason,
        content=[SimpleNamespace(type="tool_use", name=tool_name, input=input_data)],
    )


def test_structured_call_marks_system_prompt_as_ephemeral_cache(monkeypatch):
    fake = _FakeAnthropicClient(_tool_use_response("_Output", {"value": "x"}))
    monkeypatch.setattr(llm_client, "_client", lambda: fake)

    llm_client.structured_call(llm_client.ModelTier.CHEAP, "a static system prompt", "user prompt", _Output)

    system = fake.messages.last_call_kwargs["system"]
    assert isinstance(system, list)
    assert system[0]["text"] == "a static system prompt"
    assert system[0]["cache_control"] == {"type": "ephemeral"}


def test_structured_call_raises_clear_error_on_truncation(monkeypatch):
    fake = _FakeAnthropicClient(_tool_use_response("_Output", {"value": "x"}, stop_reason="max_tokens"))
    monkeypatch.setattr(llm_client, "_client", lambda: fake)

    with pytest.raises(RuntimeError, match="truncated"):
        llm_client.structured_call(llm_client.ModelTier.CHEAP, "sys", "user", _Output)


def test_structured_call_returns_validated_output(monkeypatch):
    fake = _FakeAnthropicClient(_tool_use_response("_Output", {"value": "hello"}))
    monkeypatch.setattr(llm_client, "_client", lambda: fake)

    result = llm_client.structured_call(llm_client.ModelTier.STRONG, "sys", "user", _Output)

    assert result == _Output(value="hello")


def test_ocr_page_text_marks_system_prompt_as_ephemeral_cache(monkeypatch):
    fake_response = SimpleNamespace(content=[SimpleNamespace(type="text", text="transcribed text")])
    fake = _FakeAnthropicClient(fake_response)
    monkeypatch.setattr(llm_client, "_client", lambda: fake)

    result = llm_client.ocr_page_text(b"fake-image-bytes")

    system = fake.messages.last_call_kwargs["system"]
    assert system[0]["cache_control"] == {"type": "ephemeral"}
    assert result == "transcribed text"
