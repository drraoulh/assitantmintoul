from app.services.ai.prompts import SYSTEM_PROMPT, TEXT_STYLE_PROMPT


def test_system_prompt_covers_practical_guide_topics() -> None:
    lowered = SYSTEM_PROMPT.casefold()
    for needle in (
        "transport",
        "safety",
        "scam",
        "gastronomy",
        "camfranglais",
        "itineraries",
        "douala",
        "warm",
    ):
        assert needle in lowered
    assert "short" in TEXT_STYLE_PROMPT.casefold() or "scannable" in TEXT_STYLE_PROMPT.casefold()
