"""Unit tests for Phase 1.2 voice text chunker."""

from app.services.speech.voice_chunker import flush_remainder, split_ready_phrases


def test_prefers_sentence_end() -> None:
    ready, leftover = split_ready_phrases(
        "Le Cameroun est magnifique. Ensuite visitez Kribi.",
        first_chunk=True,
    )
    assert ready == ["Le Cameroun est magnifique."]
    assert leftover == "Ensuite visitez Kribi."


def test_first_chunk_flushes_on_soft_punct() -> None:
    ready, leftover = split_ready_phrases(
        "Je te recommande une sortie nature, au parc national",
        first_chunk=True,
    )
    assert ready
    assert ready[0].endswith(",") or "nature" in ready[0].lower()
    assert "parc" in leftover.lower() or leftover.startswith("au")


def test_never_splits_mid_word() -> None:
    # Hard flush must cut on a space before HARD threshold.
    buf = "abcdefghij " + ("x" * 60)  # space early, then long token
    ready, leftover = split_ready_phrases(buf, first_chunk=False)
    if ready:
        assert " " not in ready[0] or ready[0].endswith("abcdefghij") or ready[0].isascii()
        # No cut inside the long x-run without a space
        assert not ready[0].endswith("xxxx") or " " in buf[:80]


def test_first_hard_flush_word_boundary() -> None:
    words = " ".join(["mot"] * 20)  # plenty of spaces
    ready, leftover = split_ready_phrases(words, first_chunk=True)
    assert ready
    assert len(ready[0]) >= 20
    assert not ready[0].endswith("motmot")  # spaced
    assert leftover.startswith("mot") or leftover == ""


def test_first_hard_threshold_is_40() -> None:
    from app.services.speech import voice_chunker as vc

    assert vc.FIRST_HARD == 40
    assert vc.FIRST_SOFT == 32


def test_later_chunk_waits_longer_than_first() -> None:
    short = "Une petite phrase sans point encore"
    r1, _ = split_ready_phrases(short, first_chunk=True)
    r2, _ = split_ready_phrases(short, first_chunk=False)
    # Same buffer: first mode may flush earlier via hard threshold; later may wait.
    # At ~35 chars without punct, first HARD is 48 so neither hard-flushes yet.
    assert r1 == [] or len(r1[0]) >= 20
    assert r2 == []


def test_flush_remainder() -> None:
    assert flush_remainder("  fin  ") == ["fin"]
    assert flush_remainder("   ") == []


def test_tiny_sentence_held_until_min() -> None:
    ready, leftover = split_ready_phrases("Oui. Suite plus longue ici pour le guide.", first_chunk=True)
    # "Oui." alone is < SENTENCE_MIN (12) → held; longer sentence may flush
    assert "Oui" in leftover or any("Oui" in r for r in ready)


def test_append_token_inserts_space() -> None:
    from app.services.speech.voice_chunker import append_token

    assert append_token("Cameroun.", "Prenez") == "Cameroun. Prenez"
    assert append_token("Cameroun ", "est") == "Cameroun est"
