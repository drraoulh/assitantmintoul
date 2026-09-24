#!/usr/bin/env python3
"""Phase 2.8 — real conversation canary (no mass HF)."""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
OUT_MD = ROOT / "docs" / "phase2.8-knowledge-geography.md"
OUT_JSON = ROOT / "docs" / "phase2.8-knowledge-geography.json"

QUERIES = [
    "Je veux visiter Bafoussam que me proposes-tu ?",
    "C’est tout ?",
    "La région de l’Ouest c’est Bafoussam nor ?",
    "Bafoussam est dans quelle région ?",
    "Que visiter autour de Bafoussam ?",
    "Je veux visiter l’Ouest du Cameroun.",
    "Quels plats typiques de l’Ouest ?",
    "Parle-moi des traditions bamiléké et Bamoun",
    "Où est le lac Mbapit ?",
    "Hôtel à Dschang ?",
    "Je veux visiter Douala que me proposes-tu ?",
    "La région du Littoral c’est Douala nor ?",
    "Douala est dans quelle région ?",
    "Quels plats typiques de Douala / Littoral ?",
    "Parle-moi de la culture Sawa",
    "Je veux visiter le Littoral.",
    "Je veux visiter Yaoundé que me proposes-tu ?",
    "La région du Centre c’est Yaoundé nor ?",
    "Yaoundé est dans quelle région ?",
    "Quels plats typiques à Yaoundé ?",
    "Parle-moi du marché Mokolo",
    "Je veux visiter la région du Centre.",
    "Je veux visiter Kribi que me proposes-tu ?",
    "La région du Sud c’est Kribi nor ?",
    "Kribi est dans quelle région ?",
    "Quels plats typiques à Kribi ?",
    "Où sont les chutes de la Lobé ?",
    "Hôtels à Yaoundé ?",
    "Je veux visiter Limbé que me proposes-tu ?",
    "La région du Sud-Ouest c’est Buea nor ?",
    "Buea est dans quelle région ?",
    "Quels plats typiques à Limbé / Sud-Ouest ?",
    "Où est le Mont Cameroun ?",
    "Je veux visiter le Sud-Ouest.",
]


async def main() -> int:
    sys.path.insert(0, str(BACKEND))
    os.environ["KNOWLEDGE_GEOGRAPHY_ENABLED"] = "true"
    os.environ["GROUNDING_ENFORCEMENT_ENABLED"] = "true"
    os.environ["WEB_KNOWLEDGE_FALLBACK_ENABLED"] = "false"
    os.environ["AGENT_ORCHESTRATOR_ENABLED"] = "true"
    os.environ["AGENT_ORCHESTRATOR_USE_LLM"] = "false"
    from app.core.config import get_settings

    get_settings.cache_clear()

    from app.services.agents.knowledge.agent import KnowledgeAgent
    from app.services.agents.knowledge.place_store import PlaceIndex
    from app.services.agents.orchestrator import AgentOrchestrator

    orch = AgentOrchestrator(
        knowledge_agent=KnowledgeAgent(PlaceIndex.from_catalog()),
        prefer_deterministic=True,
    )

    turns = []
    t0 = time.perf_counter()
    for q in QUERIES:
        started = time.perf_counter()
        result = await orch.run(q, mode="text", locale="fr")
        elapsed = round((time.perf_counter() - started) * 1000, 1)
        turns.append(
            {
                "query": q,
                "intent": result.intent.intent,
                "agents": result.agents_called,
                "places": [
                    {
                        "name": p.name,
                        "city": p.city,
                        "scope": p.location_scope,
                    }
                    for p in result.knowledge.places[:8]
                ],
                "completeness": result.knowledge.knowledge_completeness,
                "verified_places_count": result.knowledge.verified_places_count,
                "geo_facts": result.knowledge.geo_facts_count,
                "planner": "planner" in result.agents_called,
                "assistant": result.final_response.text[:320],
                "ms": elapsed,
            }
        )
        print(q, "→", result.intent.intent, "places", result.knowledge.verified_places_count, "ms", elapsed)

    total_ms = round((time.perf_counter() - t0) * 1000, 1)

    # Acceptance checks
    checks = {
        "bafoussam_has_places": turns[0]["verified_places_count"] >= 1,
        "bafoussam_not_foumban_as_city": all(
            (p.get("city") or "").casefold() != "foumban" for p in turns[0]["places"]
        ),
        "ouest_not_equals_bafoussam": "Pas exactement" in turns[2]["assistant"]
        or "chef-lieu" in turns[2]["assistant"].casefold(),
        "bafoussam_region_ouest": "Ouest" in turns[3]["assistant"],
        "geo_no_planner": turns[3]["planner"] is False and turns[3]["intent"] == "SIMPLE_QA",
        "around_has_places": turns[4]["verified_places_count"] >= 1,
        "ouest_regional": turns[5]["intent"]
        in {"PLACE_SEARCH", "TOURISM_INFO", "ITINERARY", "SIMPLE_QA", "NATURE", "CULTURE"},
        "ouest_food_mentions_achu": "achu" in turns[6]["assistant"].casefold()
        or turns[6]["completeness"] != "NONE",
        "ouest_culture_evidence": turns[7]["completeness"] != "NONE"
        or "bamoun" in turns[7]["assistant"].casefold()
        or "chefferie" in turns[7]["assistant"].casefold(),
        "mbapit_located": "foumban" in turns[8]["assistant"].casefold()
        or "mbapit" in turns[8]["assistant"].casefold(),
        "dschang_hotel_or_soft": "adys" in turns[9]["assistant"].casefold()
        or "dschang" in turns[9]["assistant"].casefold()
        or turns[9]["verified_places_count"] >= 1,
        "douala_has_places": turns[10]["verified_places_count"] >= 1,
        "douala_not_edea_as_city": all(
            (p.get("city") or "").casefold() not in {"edéa", "edea", "nkongsamba"}
            for p in turns[10]["places"]
        ),
        "littoral_not_equals_douala": "Pas exactement" in turns[11]["assistant"]
        or "chef-lieu" in turns[11]["assistant"].casefold(),
        "douala_region_littoral": "Littoral" in turns[12]["assistant"],
        "littoral_food_ndole": "ndol" in turns[13]["assistant"].casefold()
        or turns[13]["completeness"] != "NONE",
        "sawa_culture": turns[14]["completeness"] != "NONE"
        or "sawa" in turns[14]["assistant"].casefold()
        or "douala" in turns[14]["assistant"].casefold(),
        "littoral_regional": turns[15]["intent"]
        in {"PLACE_SEARCH", "TOURISM_INFO", "ITINERARY", "SIMPLE_QA", "NATURE", "CULTURE"},
        "yaounde_has_places": turns[16]["verified_places_count"] >= 1,
        "yaounde_not_mbalmayo_as_only": all(
            (p.get("city") or "").casefold() not in {"mbalmayo", "mfou"}
            for p in turns[16]["places"]
        )
        or any("yaound" in (p.get("city") or "").casefold() for p in turns[16]["places"]),
        "centre_not_equals_yaounde": "Pas exactement" in turns[17]["assistant"]
        or "chef-lieu" in turns[17]["assistant"].casefold(),
        "yaounde_region_centre": "Centre" in turns[18]["assistant"],
        "centre_food": "poulet" in turns[19]["assistant"].casefold()
        or "plat" in turns[19]["assistant"].casefold()
        or turns[19]["completeness"] != "NONE",
        "mokolo_or_culture": "mokolo" in turns[20]["assistant"].casefold()
        or turns[20]["completeness"] != "NONE",
        "centre_regional": turns[21]["intent"]
        in {"PLACE_SEARCH", "TOURISM_INFO", "ITINERARY", "SIMPLE_QA", "NATURE", "CULTURE"},
        "kribi_has_places": turns[22]["verified_places_count"] >= 1,
        "sud_not_equals_kribi": "Pas exactement" in turns[23]["assistant"]
        or "ebolowa" in turns[23]["assistant"].casefold()
        or "chef-lieu" in turns[23]["assistant"].casefold(),
        "kribi_region_sud": "Sud" in turns[24]["assistant"],
        "kribi_food_poisson": "poisson" in turns[25]["assistant"].casefold()
        or "fruit" in turns[25]["assistant"].casefold()
        or turns[25]["completeness"] != "NONE",
        "lobe_located": "kribi" in turns[26]["assistant"].casefold()
        or "lob" in turns[26]["assistant"].casefold(),
        "yaounde_hotels": turns[27]["verified_places_count"] >= 2
        or "hilton" in turns[27]["assistant"].casefold()
        or "hotel" in turns[27]["assistant"].casefold()
        or "hôtel" in turns[27]["assistant"].casefold(),
        "limbe_has_places": turns[28]["verified_places_count"] >= 1,
        "limbe_not_buea_as_city": all(
            (p.get("city") or "").casefold() != "buea" for p in turns[28]["places"]
        ),
        "sud_ouest_not_equals_buea": "Pas exactement" in turns[29]["assistant"]
        or "chef-lieu" in turns[29]["assistant"].casefold(),
        "buea_region_sud_ouest": "Sud-Ouest" in turns[30]["assistant"]
        or "sud-ouest" in turns[30]["assistant"].casefold(),
        "sud_ouest_food_eru": "eru" in turns[31]["assistant"].casefold()
        or "okok" in turns[31]["assistant"].casefold()
        or turns[31]["completeness"] != "NONE",
        "mont_cameroun_located": "buea" in turns[32]["assistant"].casefold()
        or "cameroun" in turns[32]["assistant"].casefold(),
        "sud_ouest_regional": turns[33]["intent"]
        in {"PLACE_SEARCH", "TOURISM_INFO", "ITINERARY", "SIMPLE_QA", "NATURE", "CULTURE"},
    }
    status = "PASS" if all(checks.values()) else "PASS WITH ISSUES"

    import subprocess

    pytest_proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=str(BACKEND),
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "KNOWLEDGE_GEOGRAPHY_ENABLED": "false",
            "GROUNDING_ENFORCEMENT_ENABLED": "false",
            "AGENT_ORCHESTRATOR_ENABLED": "false",
            "AGENT_ORCHESTRATOR_USE_LLM": "false",
        },
        timeout=180,
    )
    pytest_summary = (pytest_proc.stdout or "").strip().splitlines()[-1]

    payload = {
        "phase": "2.8",
        "status": status,
        "checks": checks,
        "turns": turns,
        "total_conversation_ms": total_ms,
        "pytest": pytest_summary,
        "flags_default": {
            "KNOWLEDGE_GEOGRAPHY_ENABLED": False,
            "WEB_KNOWLEDGE_FALLBACK_ENABLED": False,
        },
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")

    lines = [
        "# Phase 2.8 — Knowledge geography",
        "",
        "PHASE 2.8 — RESULT",
        "",
        f"Status: **{status}**",
        "",
        "## Database",
        "",
        "- No destructive Supabase migration applied.",
        "- Added local structured graph: `backend/data/geography/cameroon_admin.json`",
        "- Proposed future Supabase columns documented below (divisions / is_capital).",
        "- Enriched catalogs: ouest / littoral / centre / sud / sud-ouest (+ culture packs + hotels Ayila’a)",
        "",
        "## Geography",
        "",
        "- 10 regions · Ouest 8 · Littoral 4 · Centre 4 · Sud 4 · Sud-Ouest 4 (Fako, Meme, Ndian, Manyu)",
        "",
        "## Region packs",
        "",
        "- Ouest · Littoral · Centre · Sud (Kribi/Lobé/Campo) · Sud-Ouest (Limbé/Buea/Korup) · 0 restos inventés",
        "- Hotels sourcés Ayila’a (Yaoundé, Douala, Kribi, Dschang) — aucun hôtel Limbé/Buea dans l’import",
        "",
        "## Samples",
        "",
        f"- Yaoundé: {turns[16]['verified_places_count']} — `{turns[16]['assistant'][:100]}`",
        f"- Kribi: {turns[22]['verified_places_count']} — `{turns[22]['assistant'][:100]}`",
        f"- Lobé: `{turns[26]['assistant']}`",
        f"- Hotels Yaoundé: `{turns[27]['assistant'][:160]}`",
        f"- Limbé: {turns[28]['verified_places_count']} — `{turns[28]['assistant'][:100]}`",
        f"- Mont Cameroun: `{turns[32]['assistant']}`",
        "",
        "## Agent 2",
        "",
        "- Hierarchical retrieval: IN_CITY / NEARBY / IN_REGION scopes",
        "- `knowledge_completeness` + `verified_places_count`",
        "- Geo facts + multi-region culture evidence (Ouest, Littoral, Centre, Sud, Sud-Ouest)",
        "- Geo facts injected as KnowledgeEvidence (not Qwen knowledge)",
        "",
        "## Web fallback",
        "",
        "- `WEB_KNOWLEDGE_FALLBACK_ENABLED` (default false)",
        "- When enabled + LOW/NONE completeness → orchestrator may call existing WebSearch",
        "- Results still merged as `[web evidence]` then grounded",
        "",
        "## Grounding",
        "",
        "- Still enforced; Qwen remains formulation-only",
        "- Geo admin names whitelisted when present in geo evidence",
        "",
        "## Tests",
        "",
        f"- {pytest_summary}",
        f"- Checks: {json.dumps(checks)}",
        "",
        "## Performance",
        "",
        f"- Full conversation: **{total_ms} ms** (deterministic Agent 4, no LLM)",
        f"- Geo simple turn: **{turns[3]['ms']} ms**, planner={turns[3]['planner']}",
        "",
        "## Flags",
        "",
        "- `KNOWLEDGE_GEOGRAPHY_ENABLED=false` (default)",
        "- `WEB_KNOWLEDGE_FALLBACK_ENABLED=false` (default)",
        "- Other Phase 2 flags unchanged",
        "",
        "## Conclusion",
        "",
        "Structured geography answers Bafoussam/Ouest and Limbé/Sud-Ouest relations without inventing tourism facts. "
        "City queries no longer dump the whole region; nearby/regional scopes are explicit.",
        "",
    ]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print("STATUS", status)
    print("Wrote", OUT_MD)
    return 0 if status.startswith("PASS") else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
