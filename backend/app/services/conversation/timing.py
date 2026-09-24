"""Per-operation timings for SqlConversationStore (Phase 1.7 diagnostic)."""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Iterator

logger = logging.getLogger(__name__)


@dataclass
class StoreOpTiming:
    """One timed DB/store operation."""

    name: str
    start_ms: float
    end_ms: float
    duration_ms: float
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class StoreTrace:
    """Accumulates timings for one prepare / persist cycle."""

    wall0: float = field(default_factory=time.perf_counter)
    ops: list[StoreOpTiming] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)

    def mark(self, name: str, duration_ms: float, **extra: Any) -> None:
        now = (time.perf_counter() - self.wall0) * 1000
        op = StoreOpTiming(
            name=name,
            start_ms=round(now - duration_ms, 1),
            end_ms=round(now, 1),
            duration_ms=round(duration_ms, 1),
            extra={k: v for k, v in extra.items() if v is not None},
        )
        self.ops.append(op)
        logger.info(
            "[STORE] op=%-22s duration_ms=%7.1f start=+%.1f end=+%.1f%s",
            name,
            op.duration_ms,
            op.start_ms,
            op.end_ms,
            f" {op.extra}" if op.extra else "",
        )

    def sum(self, *names: str) -> float:
        wanted = set(names)
        return round(sum(o.duration_ms for o in self.ops if o.name in wanted), 1)

    def total_ms(self) -> float:
        return round((time.perf_counter() - self.wall0) * 1000, 1)

    def as_dict(self) -> dict[str, Any]:
        return {
            "total_ms": self.total_ms(),
            "ops": [
                {
                    "name": o.name,
                    "start_ms": o.start_ms,
                    "end_ms": o.end_ms,
                    "duration_ms": o.duration_ms,
                    **o.extra,
                }
                for o in self.ops
            ],
            "meta": dict(self.meta),
        }


@contextmanager
def timed_op(trace: StoreTrace | None, name: str, **extra: Any) -> Iterator[None]:
    t0 = time.perf_counter()
    try:
        yield
    finally:
        if trace is not None:
            trace.mark(name, (time.perf_counter() - t0) * 1000, **extra)


@asynccontextmanager
async def timed_session(
    session_factory: Any,
    trace: StoreTrace | None,
) -> AsyncIterator[Any]:
    """Open a session and measure connection acquisition (first real checkout)."""
    t_open = time.perf_counter()
    async with session_factory() as session:
        if trace is not None:
            trace.mark("session_open", (time.perf_counter() - t_open) * 1000)
        t_acq = time.perf_counter()
        # Force pool checkout (NullPool → new TLS+TCP to Supabase).
        await session.connection()
        if trace is not None:
            trace.mark(
                "db_connection_acquire",
                (time.perf_counter() - t_acq) * 1000,
            )
        yield session
