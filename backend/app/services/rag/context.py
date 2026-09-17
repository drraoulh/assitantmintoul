from app.services.rag.chunk import KnowledgeChunk


def format_knowledge_context(chunks: list[KnowledgeChunk]) -> str:
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
        blocks.append(f"{header}{meta}\n{chunk.text.strip()}")
    return "\n\n".join(blocks)


def build_system_prompt(base_prompt: str, context: str) -> str:
    if not context.strip():
        return base_prompt

    grounded = (
        f"{base_prompt.rstrip()}\n\n"
        "## Curated knowledge base excerpts\n"
        "Use the excerpts below as your primary factual ground when they are relevant. "
        "Prefer them over general memory for places, tips, and regional orientation. "
        "If the excerpts do not cover the question, say what is missing instead of inventing "
        "precise prices, schedules, or official rules.\n\n"
        f"{context.strip()}\n"
    )
    return grounded
