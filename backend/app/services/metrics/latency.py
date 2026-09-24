"""Lightweight phase timers for voice/chat latency audits."""

from __future__ import annotations

import logging
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator

logger = logging.getLogger(__name__)

# Display order for the human-readable [PERF] summary.
_PERF_ORDER = (
    "stt",
    "routing",
    "route",
    "rag",
    "web",
    "prompt",
    "grounding",
    "llm_ttft",
    "llm",
    "tts_ttfb",
    "tts_first",
    "tts",
    "first_audio",
)


@dataclass
class PhaseTimer:
    """Collect named phase durations in milliseconds."""

    label: str = "turn"
    turn_id: str = field(default_factory=lambda: uuid.uuid4().hex[:10])
    phases: dict[str, float] = field(default_factory=dict)
    started_at: float = field(default_factory=time.perf_counter)
    started_wall_ms: float = field(default_factory=lambda: time.time() * 1000)

    @contextmanager
    def phase(self, name: str) -> Iterator[None]:
        begin = time.perf_counter()
        try:
            yield
        finally:
            self.phases[name] = round((time.perf_counter() - begin) * 1000, 1)

    def mark(self, name: str, duration_ms: float) -> None:
        self.phases[name] = round(duration_ms, 1)

    def add(self, name: str, duration_ms: float) -> None:
        """Accumulate duration into an existing phase (parallel work)."""
        self.phases[name] = round(self.phases.get(name, 0.0) + duration_ms, 1)

    @property
    def total_ms(self) -> float:
        return round((time.perf_counter() - self.started_at) * 1000, 1)

    def as_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "turn_id": self.turn_id,
            "started_wall_ms": round(self.started_wall_ms, 1),
            "total_ms": self.total_ms,
            "phases_ms": dict(self.phases),
        }

    def log(self, level: int = logging.INFO) -> None:
        """Emit a compact one-line summary plus a readable [PERF] block."""
        parts = ", ".join(f"{name}={ms:.0f}ms" for name, ms in self.phases.items())
        logger.log(
            level,
            "latency[%s] turn=%s total=%.0fms %s",
            self.label,
            self.turn_id,
            self.total_ms,
            parts or "(no phases)",
        )
        for line in self.perf_lines():
            logger.log(level, "%s", line)

    def perf_lines(self) -> list[str]:
        """Human-readable Phase-1 style summary lines."""
        lines = [f"[PERF] turn={self.turn_id} label={self.label}"]
        seen: set[str] = set()
        for name in _PERF_ORDER:
            if name in self.phases:
                lines.append(f"[PERF] {name.upper():12} {self.phases[name]:7.0f} ms")
                seen.add(name)
        for name, ms in self.phases.items():
            if name not in seen:
                lines.append(f"[PERF] {name.upper():12} {ms:7.0f} ms")
        lines.append(f"[PERF] {'TOTAL':12} {self.total_ms:7.0f} ms")
        return lines
