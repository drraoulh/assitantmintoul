"""Phase 1.6 — fine-grained LLM stream chronology (diagnostic only)."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class LlmStreamTrace:
    """Monotonic timeline for one production LLM stream (voice/chat)."""

    turn_id: str
    model: str = ""
    wall0: float = field(default_factory=time.perf_counter)
    events: list[dict[str, Any]] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)

    # Explicit metric fields (ms from wall0 unless noted as delta)
    llm_prepare_ms: float | None = None
    provider_ttfh_ms: float | None = None
    stream_parse_ms: float | None = None
    app_ttft_ms: float | None = None
    first_useful_text_ms: float | None = None
    first_phrase_ready_ms: float | None = None
    generation_ms: float | None = None

    provider_attempt_count: int = 0
    retry_count: int = 0
    fallback_used: bool = False
    fallback_reason: str | None = None
    http_status: int | None = None
    cold: bool | None = None
    error: str | None = None

    # Absolute stamps for metric derivation
    _provider_call_started_at: float | None = field(default=None, repr=False)
    _provider_first_event_at: float | None = field(default=None, repr=False)
    _first_token_at: float | None = field(default=None, repr=False)

    def mark(self, name: str, **extra: Any) -> float:
        now = time.perf_counter()
        elapsed = round((now - self.wall0) * 1000, 1)
        prev = self.events[-1]["elapsed_ms"] if self.events else 0.0
        row = {
            "event": name,
            "elapsed_ms": elapsed,
            "delta_ms": round(elapsed - prev, 1),
            **{k: v for k, v in extra.items() if v is not None},
        }
        self.events.append(row)
        logger.info(
            "[VOICE][turn=%s] %-28s +%7.1fms (Δ %6.1fms)%s",
            self.turn_id,
            name,
            elapsed,
            row["delta_ms"],
            f" {extra}" if extra else "",
        )
        return elapsed

    def set_meta(self, **kwargs: Any) -> None:
        self.meta.update({k: v for k, v in kwargs.items() if v is not None})

    def note_provider_call_started(self) -> None:
        self._provider_call_started_at = time.perf_counter()
        self.provider_attempt_count += 1
        self.mark(
            "provider_call_started",
            attempt=self.provider_attempt_count,
        )
        # Prepare = time until first network dispatch
        if self.llm_prepare_ms is None:
            self.llm_prepare_ms = round(
                (self._provider_call_started_at - self.wall0) * 1000, 1
            )

    def note_http_dispatched(self) -> None:
        self.mark("http_request_dispatched", attempt=self.provider_attempt_count)

    def note_response_headers(self, status: int | None = None) -> None:
        self.http_status = status
        now = time.perf_counter()
        if self._provider_first_event_at is None:
            self._provider_first_event_at = now
            if self._provider_call_started_at is not None:
                self.provider_ttfh_ms = round(
                    (now - self._provider_call_started_at) * 1000, 1
                )
        self.mark(
            "provider_response_headers",
            http_status=status,
            provider_ttfh_ms=self.provider_ttfh_ms,
        )

    def note_stream_iterator_created(self) -> None:
        self.mark("stream_iterator_created")

    def note_first_stream_event(self, *, kind: str | None = None) -> None:
        if any(e["event"] == "first_stream_event" for e in self.events):
            return
        now = time.perf_counter()
        if self._provider_first_event_at is None:
            self._provider_first_event_at = now
            if self._provider_call_started_at is not None and self.provider_ttfh_ms is None:
                self.provider_ttfh_ms = round(
                    (now - self._provider_call_started_at) * 1000, 1
                )
        self.mark("first_stream_event", kind=kind, provider_ttfh_ms=self.provider_ttfh_ms)

    def note_first_token(self, *, chars: int | None = None) -> None:
        if self._first_token_at is not None:
            return
        now = time.perf_counter()
        self._first_token_at = now
        self.app_ttft_ms = round((now - self.wall0) * 1000, 1)
        if self._provider_first_event_at is not None:
            self.stream_parse_ms = round(
                (now - self._provider_first_event_at) * 1000, 1
            )
        self.mark(
            "first_token",
            chars=chars,
            app_ttft_ms=self.app_ttft_ms,
            stream_parse_ms=self.stream_parse_ms,
        )

    def note_first_useful_text(self, *, text: str | None = None) -> None:
        if self.first_useful_text_ms is not None:
            return
        self.first_useful_text_ms = round((time.perf_counter() - self.wall0) * 1000, 1)
        self.mark(
            "first_useful_text",
            chars=len(text or ""),
            preview=(text or "")[:48],
        )

    def note_first_phrase_ready(self, *, text: str | None = None) -> None:
        if self.first_phrase_ready_ms is not None:
            return
        self.first_phrase_ready_ms = round((time.perf_counter() - self.wall0) * 1000, 1)
        self.mark(
            "first_phrase_ready",
            chars=len(text or ""),
            preview=(text or "")[:64],
        )

    def note_fallback(self, reason: str) -> None:
        self.fallback_used = True
        self.fallback_reason = reason
        self.retry_count += 1
        self.mark("fallback_used", reason=reason, retry_count=self.retry_count)

    def note_llm_end(self) -> None:
        self.generation_ms = round((time.perf_counter() - self.wall0) * 1000, 1)
        self.mark("llm_end", generation_ms=self.generation_ms)

    def note_error(self, error: str, *, http_status: int | None = None) -> None:
        self.error = error
        if http_status is not None:
            self.http_status = http_status
        self.mark("error", error=error[:160], http_status=http_status)

    def chronology_lines(self) -> list[str]:
        lines = [f"turn={self.turn_id} model={self.model}"]
        for e in self.events:
            lines.append(
                f"{e['event']:28} +{e['elapsed_ms']:8.1f} ms  (Δ {e['delta_ms']:.1f} ms)"
            )
        return lines

    def as_dict(self) -> dict[str, Any]:
        return {
            "turn_id": self.turn_id,
            "model": self.model,
            "cold": self.cold,
            "llm_prepare_ms": self.llm_prepare_ms,
            "provider_ttfh_ms": self.provider_ttfh_ms,
            "stream_parse_ms": self.stream_parse_ms,
            "app_ttft_ms": self.app_ttft_ms,
            "first_useful_text_ms": self.first_useful_text_ms,
            "first_phrase_ready_ms": self.first_phrase_ready_ms,
            "generation_ms": self.generation_ms,
            "provider_attempt_count": self.provider_attempt_count,
            "retry_count": self.retry_count,
            "fallback_used": self.fallback_used,
            "fallback_reason": self.fallback_reason,
            "http_status": self.http_status,
            "error": self.error,
            "events": list(self.events),
            "meta": dict(self.meta),
        }
