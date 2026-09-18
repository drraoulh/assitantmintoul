from app.services.rag.chunk import KnowledgeChunk
from app.services.search.base import WebSearchHit


def format_knowledge_context(chunks: list[KnowledgeChunk], *, max_chars: int = 520) -> str:
    """Format retrieved chunks for injection into the LLM prompt."""
    if not chunks:
        return ""

    blocks: list[str] = []
    for index, chunk in enumerate(chunks, start=1):
        header = f"[{index}] {chunk.title}"
        meta_bits = []
        if chunk.city:
            meta_bits.append(f"city={chunk.city}")
        if chunk.region:
            meta_bits.append(f"region={chunk.region}")
        if chunk.source:
            meta_bits.append(f"source={chunk.source}")
        meta = f" ({', '.join(meta_bits)})" if meta_bits else ""
        body = chunk.text.strip()
        if len(body) > max_chars:
            body = body[: max_chars - 3].rstrip() + "..."
        blocks.append(f"{header}{meta}\n{body}")
    return "\n\n".join(blocks)


def format_web_context(hits: list[WebSearchHit], *, max_chars: int = 320) -> str:
    if not hits:
        return ""
    blocks: list[str] = []
    for index, hit in enumerate(hits, start=1):
        text = hit.as_text()
        if len(text) > max_chars:
            text = text[: max_chars - 3].rstrip() + "..."
        blocks.append(f"[W{index}] {text}")
    return "\n\n".join(blocks)


def build_system_prompt(
    base_prompt: str,
    knowledge_context: str = "",
    web_context: str = "",
) -> str:
    sections = [base_prompt.rstrip()]

    if knowledge_context.strip():
        sections.append(
            "## Curated knowledge base excerpts\n"
            "Use the excerpts below as your primary factual ground when they are relevant. "
            "Prefer them over general memory for places, tips, and regional orientation. "
            "If the excerpts do not cover the question, say what is missing instead of inventing "
            "precise prices, schedules, or official rules.\n\n"
            f"{knowledge_context.strip()}"
        )

    if web_context.strip():
        sections.append(
            "## Live web search results\n"
            "These snippets were retrieved from the open public web (tourism sites, blogs, "
            "news, TripAdvisor, Facebook/Instagram pages that appear in search, Wikipedia, etc.). "
            "Use them to complement the local knowledge base for broader or more recent context. "
            "Treat social and unverified pages as secondary tips, not official facts. Prefer the "
            "curated knowledge base when both cover the same place. Never invent URLs. If results "
            "conflict, say so briefly.\n\n"
            f"{web_context.strip()}"
        )

    if len(sections) == 1:
        return base_prompt
    return "\n\n".join(sections) + "\n"
