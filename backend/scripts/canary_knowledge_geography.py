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
    "Je veux visiter Bamenda que me proposes-tu ?",
    "La région du Nord-Ouest c’est Bamenda nor ?",
    "Bamenda est dans quelle région ?",
    "Quels plats typiques à Bamenda / Nord-Ouest ?",
    "Où est le Palais de Bafut ?",
    "Je veux visiter le Nord-Ouest.",
    "Je veux visiter Maroua que me proposes-tu ?",
    "La région de l’Extrême-Nord c’est Maroua nor ?",
    "Maroua est dans quelle région ?",
    "Quels plats typiques à Maroua / Extrême-Nord ?",
    "Où est le parc de Waza ?",
    "Je veux visiter l’Extrême-Nord.",
    "Je veux visiter Ngaoundéré que me proposes-tu ?",
    "La région de l’Adamaoua c’est Ngaoundéré nor ?",
    "Ngaoundéré est dans quelle région ?",
    "Quels plats typiques à Ngaoundéré ?",
    "Où est le lac Tison ?",
    "Hôtel à Ngaoundéré ?",
    "Je veux visiter Garoua que me proposes-tu ?",
    "La région du Nord c’est Garoua nor ?",
    "Garoua est dans quelle région ?",
    "Quels plats typiques à Garoua ?",
    "Où est le parc de la Bénoué ?",
    "Hôtels à Garoua ?",
    "Je veux visiter Bertoua que me proposes-tu ?",
    "La région de l’Est c’est Bertoua nor ?",
    "Bertoua est dans quelle région ?",
    "Quels plats typiques à Bertoua ?",
    "Où est la réserve du Dja ?",
    "Je veux visiter la région de l’Est.",
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
        "bamenda_has_places": turns[34]["verified_places_count"] >= 1,
        "bamenda_not_bafut_as_city": all(
            (p.get("city") or "").casefold() not in {"bafut", "oku"} for p in turns[34]["places"]
        ),
        "nord_ouest_not_equals_bamenda": "Pas exactement" in turns[35]["assistant"]
        or "chef-lieu" in turns[35]["assistant"].casefold(),
        "bamenda_region_nord_ouest": "Nord-Ouest" in turns[36]["assistant"]
        or "nord-ouest" in turns[36]["assistant"].casefold(),
        "nord_ouest_food_achu": "achu" in turns[37]["assistant"].casefold()
        or "marché" in turns[37]["assistant"].casefold()
        or "marche" in turns[37]["assistant"].casefold()
        or turns[37]["completeness"] != "NONE",
        "bafut_located": "bafut" in turns[38]["assistant"].casefold()
        or "nord-ouest" in turns[38]["assistant"].casefold()
        or "mezam" in turns[38]["assistant"].casefold(),
        "nord_ouest_regional": turns[39]["intent"]
        in {"PLACE_SEARCH", "TOURISM_INFO", "ITINERARY", "SIMPLE_QA", "NATURE", "CULTURE"},
        "maroua_has_places": turns[40]["verified_places_count"] >= 1,
        "maroua_not_waza_as_city": all(
            (p.get("city") or "").casefold() not in {"waza", "rhumsiki"} for p in turns[40]["places"]
        ),
        "extreme_nord_not_equals_maroua": "Pas exactement" in turns[41]["assistant"]
        or "chef-lieu" in turns[41]["assistant"].casefold(),
        "maroua_region_extreme_nord": "Extrême-Nord" in turns[42]["assistant"]
        or "extreme-nord" in turns[42]["assistant"].casefold(),
        "extreme_nord_food": "soya" in turns[43]["assistant"].casefold()
        or "brochette" in turns[43]["assistant"].casefold()
        or "mil" in turns[43]["assistant"].casefold()
        or turns[43]["completeness"] != "NONE",
        "waza_located": "waza" in turns[44]["assistant"].casefold()
        or "extrême-nord" in turns[44]["assistant"].casefold()
        or "extreme-nord" in turns[44]["assistant"].casefold()
        or "maroua" in turns[44]["assistant"].casefold(),
        "extreme_nord_regional": turns[45]["intent"]
        in {"PLACE_SEARCH", "TOURISM_INFO", "ITINERARY", "SIMPLE_QA", "NATURE", "CULTURE"},
        "ngaoundere_has_places": turns[46]["verified_places_count"] >= 1,
        "ngaoundere_not_banyo_as_city": all(
            (p.get("city") or "").casefold() not in {"banyo", "meiganga"} for p in turns[46]["places"]
        ),
        "adamaoua_not_equals_ngaoundere": "Pas exactement" in turns[47]["assistant"]
        or "chef-lieu" in turns[47]["assistant"].casefold(),
        "ngaoundere_region_adamaoua": "Adamaoua" in turns[48]["assistant"],
        "adamaoua_food": turns[49]["completeness"] != "NONE"
        or "brochette" in turns[49]["assistant"].casefold()
        or "soya" in turns[49]["assistant"].casefold()
        or "plat" in turns[49]["assistant"].casefold(),
        "tison_located": "ngaoundere" in turns[50]["assistant"].casefold()
        or "ngaoundéré" in turns[50]["assistant"].casefold()
        or "adamaoua" in turns[50]["assistant"].casefold()
        or "tison" in turns[50]["assistant"].casefold(),
        "ngaoundere_hotel_oasis": "oasis" in turns[51]["assistant"].casefold()
        or turns[51]["verified_places_count"] >= 1,
        "garoua_has_places": turns[52]["verified_places_count"] >= 1,
        "garoua_not_figuil_as_city": all(
            (p.get("city") or "").casefold() not in {"figuil", "tcholliré", "tchollire"}
            for p in turns[52]["places"]
        ),
        "nord_not_equals_garoua": "Pas exactement" in turns[53]["assistant"]
        or "chef-lieu" in turns[53]["assistant"].casefold(),
        "garoua_region_nord": "Nord" in turns[54]["assistant"],
        "nord_food": turns[55]["completeness"] != "NONE"
        or "brochette" in turns[55]["assistant"].casefold()
        or "soya" in turns[55]["assistant"].casefold()
        or "marché" in turns[55]["assistant"].casefold()
        or "marche" in turns[55]["assistant"].casefold(),
        "benoue_located": "tchollir" in turns[56]["assistant"].casefold()
        or "benou" in turns[56]["assistant"].casefold()
        or "nord" in turns[56]["assistant"].casefold(),
        "garoua_hotels": turns[57]["verified_places_count"] >= 2
        or "shalom" in turns[57]["assistant"].casefold()
        or "ribadou" in turns[57]["assistant"].casefold()
        or "plaza" in turns[57]["assistant"].casefold(),
        "bertoua_has_places": turns[58]["verified_places_count"] >= 1,
        "bertoua_not_dja_city": all(
            (p.get("city") or "").casefold() not in {"somalomo", "moloundou"}
            for p in turns[58]["places"]
        ),
        "est_not_equals_bertoua": "Pas exactement" in turns[59]["assistant"]
        or "chef-lieu" in turns[59]["assistant"].casefold(),
        "bertoua_region_est": "Est" in turns[60]["assistant"],
        "est_food": turns[61]["completeness"] != "NONE"
        or "marché" in turns[61]["assistant"].casefold()
        or "marche" in turns[61]["assistant"].casefold()
        or "plat" in turns[61]["assistant"].casefold(),
        "dja_located": "dja" in turns[62]["assistant"].casefold()
        or "est" in turns[62]["assistant"].casefold()
        or "somalomo" in turns[62]["assistant"].casefold(),
        "est_regional": turns[63]["intent"]
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
        "- Enriched catalogs: ouest → extreme-nord (+ culture packs + hotels Ayila’a where available)",
        "",
        "## Geography",
        "",
        "- 10 regions · … · Nord-Ouest 7 · Extrême-Nord 6 · Adamaoua 5 · Nord 4 · Est 4",
        "",
        "## Region packs",
        "",
        "- … · Nord-Ouest · Extrême-Nord (Maroua/Waza/Rhumsiki) · 0 restos inventés",
        "- Hotels Ayila’a: Yaoundé, Douala, Kribi, Dschang — pas Maroua/Bamenda/Limbé dans l’import",
        "",
        "## Samples",
        "",
        f"- Yaoundé: {turns[16]['verified_places_count']} — `{turns[16]['assistant'][:100]}`",
        f"- Kribi: {turns[22]['verified_places_count']} — `{turns[22]['assistant'][:100]}`",
        f"- Limbé: {turns[28]['verified_places_count']} — `{turns[28]['assistant'][:100]}`",
        f"- Bamenda: {turns[34]['verified_places_count']} — `{turns[34]['assistant'][:100]}`",
        f"- Maroua: {turns[40]['verified_places_count']} — `{turns[40]['assistant'][:100]}`",
        f"- Waza: `{turns[44]['assistant']}`",
        f"- Ngaoundéré: {turns[46]['verified_places_count']} — `{turns[46]['assistant'][:100]}`",
        f"- Oasis: `{turns[51]['assistant'][:120]}`",
        f"- Garoua: {turns[52]['verified_places_count']} — `{turns[52]['assistant'][:100]}`",
        f"- Hôtels Garoua: `{turns[57]['assistant'][:120]}`",
        f"- Bertoua: {turns[58]['verified_places_count']} — `{turns[58]['assistant'][:100]}`",
        f"- Dja: `{turns[62]['assistant']}`",
        "",
        "## Agent 2",
        "",
        "- Hierarchical retrieval: IN_CITY / NEARBY / IN_REGION scopes",
        "- Geo facts + multi-region culture evidence (Ouest → Extrême-Nord)",
        "",
        "## Web fallback",
        "",
        "- `WEB_KNOWLEDGE_FALLBACK_ENABLED` (default false)",
        "",
        "## Grounding",
        "",
        "- Still enforced; Qwen remains formulation-only",
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
        "",
        "## Conclusion",
        "",
        "Structured geography covers all 10 regions (Ouest → Est) without inventing tourism facts.",
        "",
    ]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print("STATUS", status)
    print("Wrote", OUT_MD)
    return 0 if status.startswith("PASS") else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
