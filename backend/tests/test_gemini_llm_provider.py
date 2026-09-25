"""LLM_PROVIDER=gemini: same pipeline, Gemini OpenAI-compatible transport."""

from __future__ import annotations

import json

import httpx
import pytest

from app.core.config import get_settings
from app.core.exceptions import HuggingFaceUnavailableError
from app.services.agents.response.evidence import AllowedEvidence
from app.services.agents.response.grounding_enforcement import validate_grounding
from app.services.agents.response.prompts import agent4_system_prompt
from app.services.ai import huggingface as hf
from app.services.ai.huggingface import HuggingFaceAIService


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setattr(hf, "_llm_paused_until", 0.0)
    monkeypatch.setenv("GEMINI_API_KEY", "g-key")
    monkeypatch.setenv("GEMINI_LLM_MODEL", "gemini-test")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _gemini(handler) -> HuggingFaceAIService:
    client = httpx.AsyncClient(
        base_url="https://generativelanguage.googleapis.com/v1beta/openai",
        transport=httpx.MockTransport(handler),
    )
    return HuggingFaceAIService(
        rag_service=object(), web_search_service=object(), client=client, provider="gemini"
    )


def test_gemini_defaults_from_settings():
    svc = _gemini(lambda r: httpx.Response(200))
    assert svc._base_url.endswith("/v1beta/openai")
    assert svc._model == "gemini-test"
    assert svc._token == "g-key"


@pytest.mark.asyncio
async def test_gemini_body_drops_qwen_fields_and_streams():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers["authorization"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200, text='data: {"choices":[{"delta":{"content":"Salut"}}]}\n\ndata: [DONE]\n\n'
        )

    svc = _gemini(handler)
    body = {"model": svc._model, "messages": [], "chat_template_kwargs": {"enable_thinking": False}}
    text = "".join([t async for t in svc._iter_completion_tokens(body)])
    assert text == "Salut"
    assert seen["auth"] == "Bearer g-key"
    assert "chat_template_kwargs" not in seen["body"]
    assert seen["body"]["reasoning_effort"] == "none"


@pytest.mark.asyncio
async def test_rate_limit_429_pauses_llm():
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(429, text='{"error":{"message":"quota"}}')

    svc = _gemini(handler)
    for _ in range(2):
        with pytest.raises(HuggingFaceUnavailableError):
            _ = [t async for t in svc._iter_completion_tokens({"messages": []})]
    assert len(calls) == 1


def test_general_knowledge_allows_known_places_but_not_prices():
    ev = AllowedEvidence(evidence_text_folded="ndole plat du littoral")
    text = "Goûtez le ndolé puis visitez le Musée maritime de Douala et la Pagode, avec du poulet DG."
    strict = validate_grounding(
        text, ev, catalog_names={"Musée maritime de Douala"}, general_knowledge=False
    )
    assert not strict.ok
    relaxed = validate_grounding(
        text, ev, catalog_names={"Musée maritime de Douala"}, general_knowledge=True
    )
    assert relaxed.ok, relaxed.violations
    priced = validate_grounding(text + " Entrée : 2000 FCFA.", ev, general_knowledge=True)
    assert any(v.kind == "unauthorized_price" for v in priced.violations)


def test_general_knowledge_prompt_toggle():
    assert "Connaissances générales" in agent4_system_prompt(
        language="fr", response_mode="text", general_knowledge=True
    )
    assert "Connaissances générales" not in agent4_system_prompt(
        language="fr", response_mode="text", general_knowledge=False
    )
