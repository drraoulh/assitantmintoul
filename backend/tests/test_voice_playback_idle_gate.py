"""Idle-gate contract for continuous voice playback (client interrupt fix).

Mirrors mobile/hooks/useContinuousVoiceSession.ts:
stream idle must not resolve on inter-sentence gaps (empty queue before
turn_done), only when generation is done and nothing remains to play.
"""

from __future__ import annotations


def maybe_resolve_stream_idle(
    *,
    turn_generation_done: bool,
    current_playing: int | None,
    sequences_remaining: int,
) -> bool:
    if not turn_generation_done:
        return False
    if current_playing is not None:
        return False
    if sequences_remaining > 0:
        return False
    return True


def should_emit_interrupted(*, had_running: bool, notify: bool) -> bool:
    return notify and had_running


def test_idle_not_resolved_between_sentences_before_turn_done() -> None:
    # Seq 0 finished; seq 1 not buffered yet — classic mid-reply gap.
    assert (
        maybe_resolve_stream_idle(
            turn_generation_done=False,
            current_playing=None,
            sequences_remaining=0,
        )
        is False
    )


def test_idle_resolved_after_turn_done_and_queue_empty() -> None:
    assert (
        maybe_resolve_stream_idle(
            turn_generation_done=True,
            current_playing=None,
            sequences_remaining=0,
        )
        is True
    )


def test_idle_waits_while_still_playing_after_turn_done() -> None:
    assert (
        maybe_resolve_stream_idle(
            turn_generation_done=True,
            current_playing=1,
            sequences_remaining=0,
        )
        is False
    )


def test_idle_waits_for_buffered_next_sequence() -> None:
    assert (
        maybe_resolve_stream_idle(
            turn_generation_done=True,
            current_playing=None,
            sequences_remaining=1,
        )
        is False
    )


def test_interrupted_only_when_turn_was_running() -> None:
    assert should_emit_interrupted(had_running=False, notify=True) is False
    assert should_emit_interrupted(had_running=True, notify=True) is True
    assert should_emit_interrupted(had_running=True, notify=False) is False
