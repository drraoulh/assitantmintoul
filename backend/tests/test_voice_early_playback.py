"""Spec tests for ordered early-play voice audio scheduling (frontend Phase early-play).

Mirrors mobile/services/voiceEarlyPlayback.ts OrderedVoiceScheduler so pytest
guards ordering / early-start invariants without a JS test runner.
"""

from __future__ import annotations

from dataclasses import dataclass, field


MIN_EARLY_PLAY_BYTES = 2048


@dataclass
class SeqState:
    parts: list[bytes] = field(default_factory=list)
    done: bool = False
    started: bool = False


@dataclass
class Action:
    type: str
    index: int = 0
    nbytes: int = 0
    progressive: bool = False


class OrderedVoiceScheduler:
    def __init__(self, prefer_early_play: bool = True) -> None:
        self.sequences: dict[int, SeqState] = {}
        self.next_play_index = 0
        self.has_started_playback = False
        self.current_playing: int | None = None
        self.prefer_early_play = prefer_early_play

    def reset(self) -> None:
        self.sequences.clear()
        self.next_play_index = 0
        self.has_started_playback = False
        self.current_playing = None

    def _ensure(self, index: int) -> SeqState:
        if index not in self.sequences:
            self.sequences[index] = SeqState()
        return self.sequences[index]

    def on_chunk(self, index: int, data: bytes, progressive: bool) -> Action:
        if not data:
            return Action("none")
        state = self._ensure(index)
        state.parts.append(data)
        if self.current_playing == index and state.started and progressive:
            return Action("append", index=index, nbytes=len(data))
        return self._try_start(index, progressive)

    def on_done(self, index: int, progressive: bool) -> Action:
        state = self._ensure(index)
        state.done = True
        if self.current_playing == index and state.started and progressive:
            return Action("end", index=index)
        if not state.started and not progressive:
            return self._try_start(index, False)
        if state.started:
            return Action("end", index=index)
        return self._try_start(index, progressive)

    def on_playback_finished(self, index: int, progressive: bool) -> Action:
        if self.current_playing == index:
            self.current_playing = None
        self.sequences.pop(index, None)
        self.next_play_index = max(self.next_play_index, index + 1)
        return self._try_start(self.next_play_index, progressive)

    def _try_start(self, index: int, progressive: bool) -> Action:
        if self.current_playing is not None:
            return Action("none")
        if index != self.next_play_index:
            return Action("none")
        state = self.sequences.get(index)
        if not state or state.started:
            return Action("none")
        total = sum(len(p) for p in state.parts)
        can_early = self.prefer_early_play and total >= MIN_EARLY_PLAY_BYTES and state.parts
        can_complete = state.done and total > 0
        if progressive and can_early:
            state.started = True
            self.has_started_playback = True
            self.current_playing = index
            return Action("start", index=index, nbytes=total, progressive=True)
        if not progressive and can_complete:
            state.started = True
            self.has_started_playback = True
            self.current_playing = index
            return Action("start", index=index, nbytes=total, progressive=False)
        return Action("none")


def _chunk(n: int = MIN_EARLY_PLAY_BYTES) -> bytes:
    return b"\x00" * n


def test_early_start_on_first_chunk_progressive():
    s = OrderedVoiceScheduler()
    a = s.on_chunk(0, _chunk(), True)
    assert a.type == "start"
    assert a.index == 0
    assert s.has_started_playback is True
    # audio_done must NOT be required to start
    a2 = s.on_done(0, True)
    assert a2.type == "end"


def test_no_start_before_audio_done_without_mse():
    s = OrderedVoiceScheduler()
    a = s.on_chunk(0, _chunk(), False)
    assert a.type == "none"
    a = s.on_done(0, False)
    assert a.type == "start"


def test_out_of_order_chunks_play_in_sequence():
    s = OrderedVoiceScheduler()
    # seq 2 arrives first — must not play
    assert s.on_chunk(2, _chunk(), True).type == "none"
    assert s.on_done(2, True).type == "none"
    # seq 0 starts immediately
    assert s.on_chunk(0, _chunk(), True).type == "start"
    s.on_done(0, True)
    # finish 0 → then 1 not ready → none; then chunk 1 starts
    assert s.on_playback_finished(0, True).type == "none"
    assert s.on_chunk(1, _chunk(), True).type == "start"
    s.on_done(1, True)
    assert s.on_playback_finished(1, True).type == "start"  # seq 2 already buffered+done
    assert s.current_playing == 2


def test_append_while_playing_same_sequence():
    s = OrderedVoiceScheduler()
    assert s.on_chunk(0, _chunk(), True).type == "start"
    a = s.on_chunk(0, _chunk(100), True)
    assert a.type == "append"
    assert a.nbytes == 100


def test_reset_clears_state():
    s = OrderedVoiceScheduler()
    s.on_chunk(0, _chunk(), True)
    s.reset()
    assert s.has_started_playback is False
    assert s.next_play_index == 0
    assert s.sequences == {}
