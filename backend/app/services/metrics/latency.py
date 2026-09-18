"""Lightweight phase timers for voice/chat latency audits."""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator

logger = logging.getLogger(__name__)


@dataclass
class PhaseTimer:
    """Collect named phase durations in milliseconds."""

    label: str = "turn"
    phases: dict[str, float] = field(default_factory=dict)
    started_at: float = field(default_factory=time.perf_counter)

    @contextmanager
    def phase(self, name: str) -> Iterator[None]:
        begin = time.perf_counter()
        try:
            yield
        finally:
            self.phases[name] = round((time.perf_counter() - begin) * 1000, 1)

    def mark(self, name: str, duration_ms: float) -> None:
        self.phases[name] = round(duration_ms, 1)

    @property
    def total_ms(self) -> float:
        return round((time.perf_counter() - self.started_at) * 1000, 1)

    def as_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "total_ms": self.total_ms,
            "phases_ms": dict(self.phases),
        }

    def log(self, level: int = logging.INFO) -> None:
        parts = ", ".join(f"{name}={ms:.0f}ms" for name, ms in self.phases.items())
        logger.log(
            level,
            "latency[%s] total=%.0fms %s",
            self.label,
            self.total_ms,
            parts or "(no phases)",
        )
