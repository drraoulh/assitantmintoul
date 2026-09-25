"""Real Gemini generateContent check. Never fakes grounding.

Run from backend/:  python scripts/gemini_live_check.py
Requires GEMINI_API_KEY. Does not print the key.
"""

from __future__ import annotations

import asyncio
import json
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import get_settings  # noqa: E402
from app.services.gemini import (  # noqa: E402
    GeminiGenerateRequest,
    GeminiService,
    GeminiServiceError,
    load_gemini_config,
)
from app.services.gemini.gemini_config import DEFAULT_TOOL_NAMES  # noqa: E402


async def _one(query: str, service: GeminiService) -> dict[str, object]:
    try:
        result = await service.generate(
            GeminiGenerateRequest(
                user_message=query,
                language="fr",
                enabled_tools=list(DEFAULT_TOOL_NAMES),
            )
        )
    except GeminiServiceError as exc:
        return {
            "query": query,
            "ok": False,
            "error": str(exc),
            "status": exc.status_code,
            "simulated": False,
        }
    return {
        "query": query,
        "ok": True,
        "model": result.model,
        "tools_used": list(result.tools_used),
        "web_sources": [item.model_dump() for item in result.web_sources[:4]],
        "map_results": [item.model_dump() for item in result.map_results[:4]],
        "warnings": list(result.warnings),
        "fallback_used": result.fallback_used,
        "text_preview": result.text[:280],
        "simulated": False,
    }


async def main() -> int:
    get_settings.cache_clear()
    cfg = load_gemini_config()
    if not cfg.api_key:
        print(json.dumps({"ok": False, "error": "GEMINI_API_KEY missing", "simulated": False}))
        return 2
    print(
        json.dumps(
            {
                "model": cfg.model,
                "fallback_model": cfg.fallback_model,
                "key_present": True,
                "simulated": False,
            },
            ensure_ascii=False,
        )
    )
    service = GeminiService(replace(cfg, tools_enabled=True, chat_enabled=True))
    rows = [await _one(query, service) for query in ("Bonjour", "Que visiter à Foumban ?")]
    print(json.dumps(rows, ensure_ascii=False, indent=2))
    return 0 if all(row["ok"] for row in rows) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
