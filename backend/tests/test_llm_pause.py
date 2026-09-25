"""Provider refusal / hang pauses the LLM so answers fall back instantly."""

from __future__ import annotations

import httpx
import pytest

from app.core.exceptions import GenerationTimeoutError, HuggingFaceUnavailableError
from app.services.ai import huggingface as hf
from app.services.ai.huggingface import HuggingFaceAIService


@pytest.fixture(autouse=True)
def _reset_pause(monkeypatch):
    monkeypatch.setattr(hf, "_llm_paused_until", 0.0)
    yield


def _service(handler) -> tuple[HuggingFaceAIService, list[int]]:
    calls: list[int] = []

    def counted(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return handler(request)

    client = httpx.AsyncClient(
        base_url="https://hf.test/v1", transport=httpx.MockTransport(counted)
    )
    svc = HuggingFaceAIService(
        rag_service=object(),
        web_search_service=object(),
        api_base_url="https://hf.test/v1",
        api_token="t",
        client=client,
    )
    return svc, calls


async def _drain(svc: HuggingFaceAIService) -> str:
    return "".join([t async for t in svc._iter_completion_tokens({"model": "m", "messages": []})])


@pytest.mark.asyncio
async def test_quota_402_pauses_further_calls():
    svc, calls = _service(lambda r: httpx.Response(402, text='{"error":"depleted"}'))
    with pytest.raises(HuggingFaceUnavailableError):
        await _drain(svc)
    with pytest.raises(HuggingFaceUnavailableError, match="paused"):
        await _drain(svc)
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_read_timeout_becomes_generation_timeout_and_pauses():
    def hang(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    svc, calls = _service(hang)
    with pytest.raises(GenerationTimeoutError):
        await _drain(svc)
    with pytest.raises(HuggingFaceUnavailableError, match="paused"):
        await _drain(svc)
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_stream_ok_when_not_paused():
    body = 'data: {"choices":[{"delta":{"content":"Bonjour"}}]}\n\ndata: [DONE]\n\n'
    svc, _ = _service(lambda r: httpx.Response(200, text=body))
    assert await _drain(svc) == "Bonjour"
