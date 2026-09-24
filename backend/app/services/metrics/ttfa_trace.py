"""Phase 1.3 — fine-grained turn chronology (diagnostic only)."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class TurnChronology:
    """Absolute + relative timestamps for one voice turn (no secrets)."""

    turn_id: str
    wall0: float = field(default_factory=time.perf_counter)
    events: list[dict[str, Any]] = field(default_factory=list)
    llm_first_token_at: float | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    def mark(
        self,
        name: str,
        *,
        sequence_id: int | None = None,
        at: float | None = None,
        **extra: Any,
    ) -> float:
        """Record an event. Optional ``at`` is an absolute ``perf_counter`` stamp."""
        now = at if at is not None else time.perf_counter()
        elapsed = round((now - self.wall0) * 1000, 1)
        from_ttft = None
        if self.llm_first_token_at is not None:
            from_ttft = round((now - self.llm_first_token_at) * 1000, 1)
        if name == "llm_first_token" and self.llm_first_token_at is None:
            self.llm_first_token_at = now
            from_ttft = 0.0
        prev_elapsed = self.events[-1]["elapsed_ms"] if self.events else 0.0
        row = {
            "event": name,
            "elapsed_ms": elapsed,
            "delta_ms": round(elapsed - prev_elapsed, 1),
            "from_llm_first_token_ms": from_ttft,
            "sequence_id": sequence_id,
            **{k: v for k, v in extra.items() if v is not None},
        }
        self.events.append(row)
        # Keep chronological order when ``at`` backfills Fish marks.
        self.events.sort(key=lambda e: e["elapsed_ms"])
        for i, e in enumerate(self.events):
            prev = self.events[i - 1]["elapsed_ms"] if i else 0.0
            e["delta_ms"] = round(e["elapsed_ms"] - prev, 1)
        extra_bits = ""
        for key in (
            "queue_wait_ms",
            "tts_worker_wait_ms",
            "connection_latency_ms",
            "ttfb_ms",
            "chars",
            "bytes",
        ):
            if key in row:
                extra_bits += f" {key}={row[key]}"
        logger.info(
            "[TTFA TRACE] turn=%s seq=%s %-28s elapsed=%7.1fms delta=%7.1fms from_ttft=%s%s",
            self.turn_id,
            sequence_id if sequence_id is not None else "-",
            name,
            elapsed,
            row["delta_ms"],
            f"{from_ttft:.1f}ms" if from_ttft is not None else "-",
            extra_bits,
        )
        return elapsed

    def ingest_tts_trace(
        self,
        fish: dict[str, Any],
        *,
        sequence_id: int | None = None,
        first_only: bool = True,
    ) -> None:
        """Merge Fish Audio ``synthesize_stream(trace=)`` dict into chronology."""
        if not fish:
            return
        mapping = (
            ("tts_request_start", "tts_request_start"),
            ("tts_connection_established", "tts_connection_established"),
            ("tts_first_byte", "tts_ttfb"),
            ("tts_first_byte", "tts_first_audio_byte"),
            ("tts_complete", "tts_response_complete"),
        )
        seen: set[str] = set()
        for src, dst in mapping:
            stamp = fish.get(src)
            if stamp is None or dst in seen:
                continue
            if first_only and any(e["event"] == dst for e in self.events):
                continue
            seen.add(dst)
            extra: dict[str, Any] = {}
            if dst == "tts_connection_established":
                extra["connection_latency_ms"] = fish.get("connection_latency_ms")
            if dst in {"tts_ttfb", "tts_first_audio_byte"}:
                extra["ttfb_ms"] = fish.get("ttfb_ms")
                if fish.get("tts_request_start") is not None:
                    extra["first_audio_generation_ms"] = round(
                        (stamp - fish["tts_request_start"]) * 1000, 1
                    )
            if dst == "tts_response_complete":
                extra["total_tts_ms"] = fish.get("total_tts_ms")
            self.mark(dst, sequence_id=sequence_id, at=float(stamp), **extra)

    def set_meta(self, **kwargs: Any) -> None:
        self.meta.update(kwargs)

    def as_dict(self) -> dict[str, Any]:
        return {
            "turn_id": self.turn_id,
            "events": list(self.events),
            "meta": dict(self.meta),
            "gaps": self.biggest_gaps(5),
        }

    def biggest_gaps(self, n: int = 5) -> list[dict[str, Any]]:
        gaps = [
            {
                "from": self.events[i - 1]["event"],
                "to": self.events[i]["event"],
                "delta_ms": self.events[i]["delta_ms"],
            }
            for i in range(1, len(self.events))
        ]
        gaps.sort(key=lambda g: g["delta_ms"], reverse=True)
        return gaps[:n]

    def chronology_lines(self) -> list[str]:
        lines = [f"turn={self.turn_id}"]
        for e in self.events:
            lines.append(
                f"{e['event']:28} +{e['elapsed_ms']/1000:7.3f} s  "
                f"(Δ {e['delta_ms']:.0f} ms)"
            )
        return lines
