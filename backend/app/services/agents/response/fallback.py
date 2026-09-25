"""Deterministic text renderer from TourismPlan / KnowledgeResult (no LLM)."""

from __future__ import annotations

import re
import unicodedata

from app.services.agents.web_research.ranker import semantic_overlap
from app.services.agents.web_research.route import extract_transport_facts, format_duration
from app.services.web_search.source_parser import extract_domain
from app.services.agents.intent.models import IntentResult
from app.services.agents.knowledge.models import KnowledgeResult
from app.services.agents.planner.models import TourismPlan


_LEAD_REASONS = {"FORCED_HOTEL_SEARCH", "FORCED_RESTAURANT_SEARCH"}


def render_deterministic(
    user_query: str,
    intent: IntentResult,
    knowledge: KnowledgeResult,
    tourism_plan: TourismPlan | None,
    *,
    language: str = "fr",
    response_mode: str = "text",
) -> str:
    text = _render_core(
        user_query,
        intent,
        knowledge,
        tourism_plan,
        language=language,
        response_mode=response_mode,
    )
    if (
        response_mode != "voice"
        and (intent.web_reason or "") in _LEAD_REASONS
        and intent.intent != "FOOD"
    ):
        leads = _web_leads(knowledge, limit=3)
        if leads:
            title = (
                "Leads found online (unverified — check before you go):"
                if language == "en"
                else "Pistes trouvées en ligne (non vérifiées — à confirmer avant d’y aller) :"
            )
            text = f"{text}\n\n{title}\n" + "\n".join(f"- {lead}" for lead in leads)
    return text


def _web_leads(knowledge: KnowledgeResult, *, limit: int) -> list[str]:
    leads: list[str] = []
    for chunk in knowledge.knowledge:
        if not (chunk.chunk_id or "").startswith("web:"):
            continue
        title = " ".join((chunk.title or "").split())[:90]
        domain = extract_domain(chunk.source_id or "")
        if not title or any(title in lead for lead in leads):
            continue
        leads.append(f"{title} ({domain})" if domain else title)
        if len(leads) >= limit:
            break
    return leads


def _render_core(
    user_query: str,
    intent: IntentResult,
    knowledge: KnowledgeResult,
    tourism_plan: TourismPlan | None,
    *,
    language: str = "fr",
    response_mode: str = "text",
) -> str:
    lang = "en" if language == "en" else "fr"
    voice = response_mode == "voice"

    if is_greeting(intent):
        return _greeting(user_query, lang)

    if intent.intent == "CLARIFICATION" or intent.confidence < 0.6:
        return _clarification(intent, lang)

    if intent.intent == "BOOKING":
        return _booking_unavailable(lang, has_places=bool(knowledge.places))

    # Phase 2.8 — prefer structured geo facts when present
    geo_chunks = [
        k for k in knowledge.knowledge if (k.chunk_id or "").startswith("geo-")
    ]
    if geo_chunks and intent.intent in {"SIMPLE_QA", "TOURISM_INFO", "PLACE_DETAILS"}:
        return geo_chunks[0].content.split(" (source:")[0].strip()

    if is_general_fact(intent):
        return _render_general_fact(user_query, knowledge, lang=lang, voice=voice)

    if intent.intent == "TRAVEL_ROUTE" and intent.destination:
        return _render_travel_route(intent, knowledge, lang=lang, voice=voice)
    if intent.intent == "IMAGE_SEARCH":
        return _render_image_search(intent, knowledge, lang=lang, voice=voice)
    if intent.intent == "FOOD" and intent.web_reason == "FORCED_RESTAURANT_SEARCH":
        return _render_restaurants(intent, knowledge, lang=lang, voice=voice)
    if intent.intent == "FOOD" and intent.dish:
        return _render_dish(intent, knowledge, lang=lang, voice=voice)

    culture_chunks = [
        k for k in knowledge.knowledge if (k.source_id or "").startswith("culture:")
    ]
    food_doc_chunks = [
        k
        for k in knowledge.knowledge
        if (k.source_id or "").startswith("documents/food")
        or (k.chunk_id or "").startswith("doc:food")
        or "nourriture" in (k.title or "").casefold()
        or "plats" in (k.title or "").casefold()
        or "cuisine" in (k.title or "").casefold()
    ]
    if intent.intent == "FOOD" and culture_chunks:
        return _render_culture_food(culture_chunks, knowledge, lang=lang, voice=voice)
    if intent.intent == "FOOD" and food_doc_chunks:
        # Prefer gastronomy notes over unrelated SW place cards
        slim = knowledge.model_copy(deep=True)
        slim.knowledge = food_doc_chunks
        slim.places = []
        return _render_knowledge(slim, lang=lang, voice=voice)
    if intent.intent == "CULTURE" and culture_chunks:
        return _render_culture_traditions(
            culture_chunks, knowledge, lang=lang, voice=voice
        )

    # WEB_SEARCH with web evidence — prefer knowledge/web over places
    web_chunks = [
        k for k in knowledge.knowledge if "[web evidence" in (k.content or "").casefold()
    ]
    if intent.intent == "WEB_SEARCH" and (web_chunks or knowledge.knowledge):
        return _render_web_search(user_query, knowledge, lang=lang, voice=voice)
    if (
        intent.intent in {"CULTURE", "TOURISM_INFO", "SIMPLE_QA"}
        and web_chunks
        and not (tourism_plan and tourism_plan.selected_places)
    ):
        return _render_web_search(user_query, knowledge, lang=lang, voice=voice)

    if (
        intent.destination
        and intent.intent in {"ITINERARY", "BUDGET_TRIP"}
        and not (tourism_plan and tourism_plan.days and tourism_plan.selected_places)
    ):
        return _render_travel_route(intent, knowledge, lang=lang, voice=voice)

    if tourism_plan is not None and tourism_plan.feasibility == "INSUFFICIENT_DATA":
        if not tourism_plan.selected_places and not knowledge.places and not knowledge.knowledge:
            return _insufficient(lang)

    if (
        tourism_plan is not None
        and tourism_plan.feasibility == "NOT_FEASIBLE"
        and not tourism_plan.selected_places
    ):
        return _not_feasible(tourism_plan, lang)

    if tourism_plan is not None and tourism_plan.days and tourism_plan.selected_places:
        plan_text = _render_plan(tourism_plan, knowledge, lang=lang, voice=voice)
        if intent.destination and not voice:
            route, _ = _route_section(intent, knowledge, lang=lang)
            return f"{route}\n\n{plan_text}"
        return plan_text

    if intent.intent == "PLACE_DETAILS" and knowledge.places:
        return _render_place_details(knowledge.places[0], lang=lang, voice=voice)

    if intent.intent == "HOTEL" and not knowledge.places and not any(
        (k.chunk_id or "").startswith("culture-hotel-") and "-policy-" not in (k.chunk_id or "")
        for k in knowledge.knowledge
    ):
        where = intent.city or intent.region
        if lang == "en":
            return f"I don't have a verified hotel{f' in {where}' if where else ''} yet."
        return f"Je n’ai pas encore d’hôtel vérifié{f' à {where}' if where else ''}."

    if knowledge.places:
        return _render_place_list(knowledge, intent, lang=lang, voice=voice)

    if knowledge.knowledge:
        return _render_knowledge(knowledge, lang=lang, voice=voice)

    return _insufficient(lang)


def is_greeting(intent: IntentResult) -> bool:
    return (intent.reason or "").endswith("greeting")


def is_general_fact(intent: IntentResult) -> bool:
    return intent.intent == "SIMPLE_QA" and (
        (intent.reason or "") == "general_fact"
        or intent.web_reason == "FORCED_CURRENT_INFORMATION"
    )


_FR_HINT = re.compile(r"\b(?:le|la|les|est|du|des|une?|depuis|et|au|en)\b", re.IGNORECASE)
_EN_HINT = re.compile(r"\b(?:the|is|of|since|and|has|was|in)\b", re.IGNORECASE)
_SOCIAL_DOMAINS = re.compile(r"(?:^|\.)(?:facebook|instagram|x|twitter|tiktok|youtube|linkedin)\.com$")
_SOCIAL_NOISE = re.compile(
    r"[\d\s.,]+(?:[kKmM]\s*)?(?:followers?|abonnés|likes?|j['’]aime|talking about this|"
    r"en parlent|views?|vues)\b\s*[·.]?",
    re.IGNORECASE,
)


def _render_general_fact(
    user_query: str, knowledge: KnowledgeResult, *, lang: str, voice: bool
) -> str:
    """One direct answer from the best web snippet — no place cards, no « which city? »."""
    candidates: list[tuple[float, str, str]] = []
    for chunk in knowledge.knowledge:
        content = chunk.content or ""
        if not (chunk.chunk_id or "").startswith("web:") or "low confidence" in content.casefold():
            continue
        first_line = content.split("\n", 1)[0]
        text = _SOCIAL_NOISE.sub("", re.sub(r"^\[web evidence[^\]]*\]\s*", "", first_line)).strip(" ·.-")
        if not text:
            continue
        domain = extract_domain(chunk.source_id or "")
        hint = _EN_HINT if lang == "en" else _FR_HINT
        score = semantic_overlap(text, user_query) + 0.05 * (chunk.score or 0)
        score += 0.3 if len(hint.findall(text)) >= 2 else 0.0
        score += 0.3 if first_line.startswith("[web evidence — institutional]") else 0.0
        score -= 0.6 if _SOCIAL_DOMAINS.search(domain) else 0.0
        candidates.append((score, text, domain))
    if not candidates:
        return (
            "I couldn't verify this online right now. Please try again in a moment."
            if lang == "en"
            else "Je n’ai pas pu vérifier cette information en ligne pour le moment. Réessayez dans un instant."
        )
    candidates.sort(key=lambda c: c[0], reverse=True)
    _, text, domain = candidates[0]
    if len(text) > 300:
        text = text[:299].rsplit(" ", 1)[0] + "…"
    if voice or not domain:
        return text
    return f"{text}\n\nSource: {domain}" if lang == "en" else f"{text}\n\nSource : {domain}"


def _greeting(user_query: str, lang: str) -> str:
    thanks = any(t in (user_query or "").casefold() for t in ("merci", "thank"))
    if lang == "en":
        if thanks:
            return "You're welcome! Ask me anything else about travelling in Cameroon."
        return (
            "Hello! I'm SmartMboa, your Cameroon travel guide. Ask me about places "
            "to visit, traditional food, an itinerary or hotels."
        )
    if thanks:
        return "Avec plaisir ! Posez-moi une autre question sur le Cameroun."
    return (
        "Bonjour ! Je suis SmartMboa, votre guide touristique du Cameroun. "
        "Demandez-moi des lieux à visiter, des plats traditionnels, un itinéraire "
        "ou un hôtel."
    )


def _clarification(intent: IntentResult, lang: str) -> str:
    if lang == "en":
        if intent.duration_days is None and intent.needs_planner:
            return "How many days would you like to spend in Cameroon?"
        if intent.city is None and intent.needs_places:
            return "Which city or region would you like to visit?"
        return "Could you tell me a bit more about what you are looking for?"
    if intent.duration_days is None and intent.needs_planner:
        return "Combien de jours souhaitez-vous passer au Cameroun ?"
    if intent.city is None and intent.needs_places:
        return "Quelle ville ou région souhaitez-vous visiter ?"
    return "Pouvez-vous préciser un peu ce que vous recherchez ?"


def _insufficient(lang: str) -> str:
    if lang == "en":
        return (
            "I currently do not have enough verified information "
            "to build a reliable answer for this request."
        )
    return (
        "Je dispose actuellement de trop peu d'informations vérifiées "
        "pour construire une réponse fiable à cette demande."
    )


def _booking_unavailable(lang: str, *, has_places: bool) -> str:
    if lang == "en":
        if has_places:
            return (
                "I can share general hotel information from verified sources, "
                "but live availability and real-time booking are not confirmed yet "
                "on this platform."
            )
        return (
            "I can provide tourism information, but live hotel availability "
            "and real-time booking are not confirmed yet on this platform."
        )
    if has_places:
        return (
            "Je peux partager des informations générales sur les hébergements "
            "à partir de sources vérifiées, mais la disponibilité en temps réel "
            "et la réservation ne sont pas encore confirmées sur cette plateforme."
        )
    return (
        "Je peux fournir des informations touristiques, mais la disponibilité "
        "en temps réel et la réservation d'hôtel ne sont pas encore confirmées "
        "sur cette plateforme."
    )


def _not_feasible(plan: TourismPlan, lang: str) -> str:
    warnings = "; ".join(plan.warnings[:2]) if plan.warnings else ""
    missing = ", ".join(plan.missing_information[:3]) if plan.missing_information else ""
    if lang == "en":
        parts = ["This trip plan is not feasible with the verified data available."]
        if warnings:
            parts.append(warnings)
        if missing:
            parts.append(f"Missing: {missing}.")
        if plan.budget_status and plan.budget_status != "UNKNOWN":
            parts.append(f"Budget status: {plan.budget_status}.")
        return " ".join(parts)
    parts = [
        "Ce programme n'est pas réalisable avec les données vérifiées disponibles."
    ]
    if warnings:
        parts.append(warnings)
    if missing:
        parts.append(f"Informations manquantes : {missing}.")
    if plan.budget_status and plan.budget_status != "UNKNOWN":
        parts.append(f"Statut budget : {plan.budget_status}.")
    return " ".join(parts)


def _render_plan(
    plan: TourismPlan,
    knowledge: KnowledgeResult,
    *,
    lang: str,
    voice: bool,
) -> str:
    parts: list[str] = []
    if lang == "en":
        parts.append(
            f"Here is a {plan.duration_days}-day outline based on verified places."
            if plan.duration_days > 1
            else "Here is a verified outline based on available places."
        )
    else:
        parts.append(
            f"Voici un programme sur {plan.duration_days} jours à partir de lieux vérifiés."
            if plan.duration_days > 1
            else "Voici une proposition basée sur les lieux vérifiés disponibles."
        )

    for day in plan.days:
        if not day.places:
            continue
        if voice:
            names = ", ".join(item.place_name for item in day.places)
            if lang == "en":
                parts.append(f"Day {day.day}: {names}.")
            else:
                parts.append(f"Jour {day.day} : {names}.")
            continue

        header = day.title or (f"Day {day.day}" if lang == "en" else f"Jour {day.day}")
        parts.append(f"### {header}" if not voice else header)
        for item in day.places:
            line = f"- {item.place_name}"
            details: list[str] = []
            if item.estimated_duration_hours is not None:
                details.append(
                    f"{item.estimated_duration_hours} h"
                    if lang == "en"
                    else f"{item.estimated_duration_hours} h"
                )
            if item.estimated_cost_xaf is not None:
                details.append(f"{item.estimated_cost_xaf} XAF")
            elif "estimated_cost_xaf" in plan.missing_information or item.estimated_cost_xaf is None:
                # Only mention missing cost when relevant — keep short
                pass
            if item.distance_from_previous_km is not None:
                if lang == "en":
                    details.append(
                        f"~{item.distance_from_previous_km} km as the crow flies"
                    )
                else:
                    details.append(
                        f"~{item.distance_from_previous_km} km à vol d'oiseau"
                    )
            if details:
                line += f" ({'; '.join(details)})"
            parts.append(line)

    parts.append(_budget_sentence(plan, lang))
    missing = _missing_sentence(plan.missing_information or knowledge.missing_information, lang)
    if missing:
        parts.append(missing)

    text = "\n".join(p for p in parts if p)
    if voice:
        text = text.replace("### ", "").replace("\n", " ")
        text = " ".join(text.split())
    return text.strip()


def _budget_sentence(plan: TourismPlan, lang: str) -> str:
    if plan.budget_status == "WITHIN_BUDGET" and plan.total_estimated_cost_xaf is not None:
        if lang == "en":
            return (
                f"Documented costs are about {plan.total_estimated_cost_xaf} XAF"
                + (
                    f" within your budget of {plan.budget_xaf} XAF."
                    if plan.budget_xaf
                    else "."
                )
            )
        return (
            f"Les coûts documentés représentent environ {plan.total_estimated_cost_xaf} FCFA"
            + (
                f" sur votre budget de {plan.budget_xaf} FCFA."
                if plan.budget_xaf
                else "."
            )
        )
    if plan.budget_status == "PARTIAL":
        known = plan.known_cost_xaf
        if lang == "en":
            base = (
                f"Documented costs currently total {known} XAF."
                if known is not None
                else "Some costs are still unknown."
            )
            return base + " The full total cannot be confirmed yet."
        base = (
            f"Les coûts actuellement documentés représentent {known} FCFA."
            if known is not None
            else "Certains coûts ne sont pas encore renseignés."
        )
        return base + " Le total ne peut donc pas être confirmé."
    if plan.budget_status == "OVER_BUDGET" and plan.total_estimated_cost_xaf is not None:
        if lang == "en":
            return (
                f"Documented costs ({plan.total_estimated_cost_xaf} XAF) exceed "
                f"the stated budget of {plan.budget_xaf} XAF."
            )
        return (
            f"Les coûts documentés ({plan.total_estimated_cost_xaf} FCFA) dépassent "
            f"le budget indiqué de {plan.budget_xaf} FCFA."
        )
    return ""


def _missing_sentence(missing: list[str], lang: str) -> str:
    if not missing:
        return ""
    labels_fr = {
        "opening_hours": "les horaires d'ouverture",
        "current_price": "le prix actuel",
        "estimated_cost_xaf": "certains tarifs",
        "duration_days": "la durée du séjour",
        "transport cost unavailable": "le coût du transport",
        "live_availability": "les disponibilités actuelles",
    }
    labels_en = {
        "opening_hours": "current opening hours",
        "current_price": "the current price",
        "estimated_cost_xaf": "some fees",
        "duration_days": "trip duration",
        "transport cost unavailable": "transport costs",
        "live_availability": "live availability",
    }
    labels = labels_en if lang == "en" else labels_fr
    named = [labels.get(m, m) for m in missing[:3]]
    joined = ", ".join(named)
    if lang == "en":
        return f"Not listed in my verified data: {joined}."
    return f"Non renseigné dans mes données vérifiées : {joined}."


def _web_facts(knowledge: KnowledgeResult, *, limit: int) -> list[str]:
    facts: list[str] = []
    for chunk in knowledge.knowledge:
        content = chunk.content or ""
        lowered = content.casefold()
        if (
            "[web evidence" not in lowered
            or "[web evidence — community]" in lowered
            or "[web evidence — low confidence]" in lowered
        ):
            continue
        text = content.split("\n", 1)[0]
        for prefix in ("[web evidence — institutional]", "[web evidence — unverified]"):
            text = text.replace(prefix, "")
        text = " ".join(text.split())
        if len(text) > 220:
            text = text[:219].rstrip() + "…"
        if text and text not in facts:
            facts.append(text)
        if len(facts) >= limit:
            break
    return facts


_EVENT_QUERY = re.compile(
    r"\b(?:festival|festivals|[ée]v[ée]nements?|events?|foires?|concerts?|"
    r"agenda|programme|ce mois|this month|cette semaine|this week|actualit[ée]s?)\b",
    re.IGNORECASE,
)
_EVENT_FACT = re.compile(
    r"\b(?:festivals?|f[êe]tes?|foires?|concerts?|c[ée]l[ée]brations?|ngondo|nguon|"
    r"lela|salons?|[ée]ditions?|carnavals?|events?|[ée]v[ée]nements?|fair|fest)\b",
    re.IGNORECASE,
)


def _first_section(text: str, *, limit: int) -> str:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    body = " ".join(ln.lstrip("#").strip() for ln in lines)
    body = " ".join(body.split())
    if len(body) > limit:
        body = body[: limit - 1].rsplit(" ", 1)[0] + "…"
    return body


def _render_web_search(
    user_query: str, knowledge: KnowledgeResult, *, lang: str, voice: bool
) -> str:
    facts = _web_facts(knowledge, limit=3)
    event_query = bool(_EVENT_QUERY.search(user_query or ""))
    if event_query:
        facts = [f for f in facts if _EVENT_FACT.search(f)]
    kb_chunks = [
        k.content
        for k in knowledge.knowledge
        if k.content and "[web evidence" not in k.content.casefold()
    ]
    if event_query:
        kb_chunks = [c for c in kb_chunks if _EVENT_FACT.search(c)]
    else:
        kb_chunks = [c for c in kb_chunks if semantic_overlap(c, user_query) >= 0.34]
    kb_note = _first_section(kb_chunks[0], limit=320) if kb_chunks else ""

    parts: list[str] = []
    if facts:
        intro = (
            "From the web sources I consulted:"
            if lang == "en"
            else "D’après les sources web consultées :"
        )
        parts.append(intro + "\n" + "\n".join(f"- {f}" for f in facts))
    elif event_query:
        parts.append(
            "I couldn't find a dated, verified event programme for this period."
            if lang == "en"
            else "Je n’ai pas trouvé de programme d’événements daté et vérifié pour cette période."
        )
    if kb_note:
        parts.append(kb_note)
    if not parts:
        return _insufficient(lang)
    if voice:
        return " ".join(" ".join(parts).split())[:500]
    parts.append(
        "Check the official sources listed below, or tell me a city to narrow it down."
        if lang == "en"
        else "Consultez les sources officielles ci-dessous, ou indiquez-moi une ville pour affiner."
    )
    return "\n\n".join(parts)


def _render_culture_food(
    culture_chunks,
    knowledge: KnowledgeResult,
    *,
    lang: str,
    voice: bool,
) -> str:
    dishes = [
        k
        for k in culture_chunks
        if (k.chunk_id or "").startswith("culture-dish-")
    ]
    if not dishes:
        dishes = [k for k in culture_chunks if "dish" in (k.chunk_id or "")]
    policy = [k for k in culture_chunks if "resto-policy" in (k.chunk_id or "")]
    parts: list[str] = []
    web = [] if voice else _web_points(knowledge, limit=3)
    if web:
        parts.append(
            "What the web sources I consulted say:"
            if lang == "en"
            else "Ce que disent les sources web consultées :"
        )
        parts.append(_bullets(web))
        parts.append(
            "\nComplement from my knowledge base:"
            if lang == "en"
            else "\nComplément de ma base :"
        )
    elif lang == "en":
        parts.append("Typical dishes documented in my knowledge base:")
    else:
        parts.append("Plats typiques documentés dans ma base :")
    for d in dishes[: 3 if web else 5]:
        title = d.title or "Plat"
        body = (d.content or "").strip()
        parts.append(f"- {title} : {body}" if not voice else f"{title}: {body}")
    if policy:
        parts.append(
            "Aucun restaurant n'est encore vérifié dans ma base pour cette région."
            if lang != "en"
            else "No restaurant is verified in my knowledge base for this region yet."
        )
    web_facts = [] if web else _web_facts(knowledge, limit=2)
    if web_facts and not voice:
        parts.append(
            "Complément issu de sources web consultées :"
            if lang != "en"
            else "Additional notes from consulted web sources:"
        )
        parts.extend(f"- {fact}" for fact in web_facts)
    hotels = []
    for p in knowledge.places:
        cat = p.category
        if isinstance(cat, list):
            cat_blob = " ".join(str(c) for c in cat).casefold()
        else:
            cat_blob = (cat or "").casefold()
        name_blob = (p.name or "").casefold()
        if "hotel" in cat_blob or "hôtel" in cat_blob or "hôtel" in name_blob or "hotel" in name_blob:
            hotels.append(p)
    if hotels and lang == "fr":
        parts.append(
            f"Hébergement documenté avec restauration mentionnée : {hotels[0].name}."
        )
    elif hotels:
        parts.append(f"Documented lodging with mentioned dining: {hotels[0].name}.")
    text = "\n".join(parts) if not voice else " ".join(parts)
    return text.strip()


def _render_culture_traditions(
    culture_chunks,
    knowledge: KnowledgeResult,
    *,
    lang: str,
    voice: bool,
) -> str:
    trads = [k for k in culture_chunks if (k.chunk_id or "").startswith("culture-trad-")]
    overview = [k for k in culture_chunks if (k.chunk_id or "").startswith("culture-overview-")]
    parts: list[str] = []
    if overview:
        parts.append(overview[0].content.strip())
    if lang == "en":
        parts.append("Documented cultural notes:")
    else:
        parts.append("Repères culturels documentés :")
    for t in (trads or culture_chunks)[:5]:
        title = t.title or "Culture"
        body = (t.content or "").strip()
        if overview and (t.chunk_id or "").startswith("culture-overview-"):
            continue
        parts.append(f"- {title} : {body}" if not voice else f"{title}: {body}")
    region_places = knowledge.places[:4]
    if region_places:
        names = ", ".join(p.name for p in region_places)
        if lang == "en":
            parts.append(f"Related verified places: {names}.")
        else:
            parts.append(f"📍 Lieux référencés dans SmartMboa : {names}.")
    text = "\n".join(parts) if not voice else " ".join(parts)
    return text.strip()


def _render_place_details(place, *, lang: str, voice: bool) -> str:
    bits: list[str] = []
    if lang == "en":
        bits.append(f"{place.name}" + (f" is in {place.city}." if place.city else "."))
    else:
        bits.append(f"{place.name}" + (f" se trouve à {place.city}." if place.city else "."))
    if place.description:
        bits.append(place.description.strip())
    if place.cultural_info:
        bits.append(place.cultural_info.strip())
    if place.eco_info:
        bits.append(place.eco_info.strip())
    if place.activities:
        acts = ", ".join(place.activities[:5])
        bits.append(
            f"Documented activities: {acts}."
            if lang == "en"
            else f"Activités documentées : {acts}."
        )
    if place.estimated_cost_xaf is not None:
        bits.append(
            f"Documented cost: {place.estimated_cost_xaf} XAF."
            if lang == "en"
            else f"Coût documenté : {place.estimated_cost_xaf} FCFA."
        )
    if place.recommended_duration_hours is not None:
        bits.append(
            f"Recommended duration: about {place.recommended_duration_hours} hours."
            if lang == "en"
            else f"Durée recommandée : environ {place.recommended_duration_hours} heures."
        )
    text = " ".join(bits)
    if voice:
        text = " ".join(text.split())
    return text


def _render_place_list(
    knowledge: KnowledgeResult,
    intent: IntentResult,
    *,
    lang: str,
    voice: bool,
) -> str:
    names: list[str] = []
    for p in knowledge.places[:8]:
        label = p.name
        if getattr(p, "location_scope", None) == "NEARBY":
            if lang == "en":
                label = f"{p.name} (near {intent.city or p.city or 'the area'})"
            else:
                label = f"{p.name} (environs de {intent.city or p.city or 'la zone'})"
        names.append(label)
    if not names:
        return _insufficient(lang)

    count = knowledge.verified_places_count or len(knowledge.places)
    completeness = knowledge.knowledge_completeness or "MEDIUM"

    if voice:
        joined = ", ".join(names)
        if lang == "en":
            where = f" in {intent.city}" if intent.city else ""
            base = f"SmartMboa lists {count} place(s){where}: {joined}."
            if completeness in {"LOW", "MEDIUM"} and count <= 3:
                base += " I can present these, or look for more recent tourist information if you want."
            return base
        where = f" à {intent.city}" if intent.city else ""
        base = f"SmartMboa référence {count} lieu(x){where} : {joined}."
        if completeness in {"LOW", "MEDIUM"} and count <= 3:
            base += (
                " Je peux te les présenter, ou rechercher davantage d’activités "
                "et de sites touristiques récents si tu veux."
            )
        return base

    bullets = "\n".join(f"- {n}" for n in names)
    web = _web_points(knowledge, limit=2, keep=_ACTIVITY, mentions=intent.city)
    if web:
        bullets += "\n\n" + ("🌐 Results found on the web:" if lang == "en" else "🌐 Résultats trouvés sur le Web :") + "\n" + _bullets(web)
    if lang == "en":
        header = "📍 Places listed in SmartMboa"
        if intent.city:
            header += f" for {intent.city}"
        header += f" ({count}):"
        footer = ""
        if completeness in {"LOW", "MEDIUM"} and count <= 3:
            footer = (
                "\n\nI can present these places, or search for more recent "
                "tourist activities and sites if you want."
            )
        return f"{header}\n{bullets}{footer}"
    header = "📍 Lieux référencés dans SmartMboa"
    if intent.city:
        header += f" autour de {intent.city}"
    header += f" ({count}) :"
    footer = ""
    if completeness in {"LOW", "MEDIUM"} and count <= 3:
        footer = (
            "\n\nJe peux te présenter ces lieux, ou rechercher davantage "
            "d’activités et de sites touristiques récents si tu veux."
        )
    return f"{header}\n{bullets}{footer}"


def _render_knowledge(knowledge: KnowledgeResult, *, lang: str, voice: bool) -> str:
    chunks = [c.content.strip() for c in knowledge.knowledge if c.content][:5]
    if not chunks:
        return _insufficient(lang)

    web_chunks = [c for c in chunks if "[web evidence" in c.casefold()]
    kb_chunks = [c for c in chunks if "[web evidence" not in c.casefold()]

    def _clean(text: str) -> str:
        for prefix in (
            "[web evidence — institutional]",
            "[web evidence — unverified]",
            "[web evidence — unverified] ",
            "[web evidence — community]",
            "[web evidence — low confidence]",
            "Key facts:",
        ):
            text = text.replace(prefix, "")
        return " ".join(text.split())

    if web_chunks and not kb_chunks:
        facts = [_clean(c) for c in web_chunks]
        body = " ".join(facts)[:900]
        if voice:
            return body[:500]
        if lang == "en":
            return (
                "Based on consulted web sources (not a substitute for verified "
                f"SmartMboa knowledge):\n{body}\n\n"
                "Would you like me to refine this for a specific city?"
            )
        return (
            "D’après des sources web consultées (complément lorsque la base "
            f"SmartMboa est insuffisante) :\n{body}\n\n"
            "Souhaitez-vous que je précise pour une ville (Buea, Limbe, …) ?"
        )

    body = "\n\n".join(_clean(_first_section(c, limit=380)) for c in chunks[:2])
    if voice:
        return " ".join(body.split())[:500]
    title = "From verified notes:" if lang == "en" else "D’après les notes vérifiées :"
    return f"{title}\n{body}"


_WEB_PREFIX = re.compile(r"^\s*\[web evidence[^\]]*\]\s*", re.IGNORECASE)
_TRANSPORT = re.compile(
    r"\b(?:bus|cars?|agences?|agency|agencies|compagnies?|compan(?:y|ies)|taxis?|trajets?|"
    r"routes?|km|kilom\w*|heures?|hours?|minutes|trains?|vols?|flights?|avion|voyages?|"
    r"travel\w*|transport\w*|driv\w*|d[ée]parts?|gares?|stations?|motor\s?parks?|"
    r"autoroute|highway|distance|via)\b",
    re.IGNORECASE,
)
_ACTIVITY = re.compile(
    r"\b(?:visit\w*|randonn\w*|mont|mount|mus[ée]es?|museums?|jardins?|gardens?|zoo|lacs?|"
    r"lakes?|plages?|beach\w*|hik\w*|attractions?|activit\w*|sites?|palais|palace|tours?|"
    r"things\s+to\s+do|que\s+faire|[àa]\s+voir)\b",
    re.IGNORECASE,
)
_RESTAURANT_TERMS = re.compile(
    r"\b(?:restaurants?|restos?|maquis|snacks?|bars?|menu|grill|eatery|eateries|cafeteria|"
    r"serves?|sert|servent|chez)\b",
    re.IGNORECASE,
)


def _fold(text: str | None) -> str:
    decomposed = unicodedata.normalize("NFKD", (text or "").casefold())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def _web_points(
    knowledge: KnowledgeResult,
    *,
    limit: int,
    keep: re.Pattern[str] | None = None,
    exclude: set[str] | None = None,
    mentions: str | None = None,
) -> list[tuple[str, str]]:
    """(snippet, domain) pairs straight from web evidence — never rewritten.

    Social-media posts come last and hashtag-heavy snippets are skipped.
    """
    candidates: list[tuple[bool, str, str, str]] = []
    for chunk in knowledge.knowledge:
        if not (chunk.chunk_id or "").startswith("web:"):
            continue
        if "low confidence" in (chunk.content or "")[:40].casefold():
            continue
        if exclude and chunk.chunk_id in exclude:
            continue
        raw = _WEB_PREFIX.sub("", (chunk.content or "").split("\n", 1)[0])
        text = _SOCIAL_NOISE.sub("", " ".join(raw.split())).lstrip("-–·•* ").strip()
        if not text or text.count("#") >= 2:
            continue
        domain = extract_domain(chunk.source_id or "")
        blob = f"{chunk.title or ''} {text}"
        if keep is not None and not keep.search(blob):
            continue
        if mentions and _fold(mentions) not in _fold(f"{blob} {domain}"):
            continue
        if len(text) > 240:
            text = text[:239].rsplit(" ", 1)[0] + "…"
        if any(text == c[1] for c in candidates):
            continue
        candidates.append((bool(_SOCIAL_DOMAINS.search(domain)), text, domain, chunk.chunk_id))
    candidates.sort(key=lambda c: c[0])
    points = [(text, domain) for _, text, domain, _ in candidates[:limit]]
    if exclude is not None:
        exclude.update(c[3] for c in candidates[:limit])
    return points


def _bullets(points: list[tuple[str, str]]) -> str:
    return "\n".join(f"- {text}" + (f" ({domain})" if domain else "") for text, domain in points)


def _web_chunks(knowledge: KnowledgeResult, phase: str) -> list[tuple[str, str, bool, str]]:
    """(snippet, domain, reverse, title) for web evidence tagged with ``phase`` by the web agent."""
    out: list[tuple[str, str, bool]] = []
    for chunk in knowledge.knowledge:
        cid = chunk.chunk_id or ""
        tags = cid.split(":")[3:]
        if not cid.startswith("web:") or phase not in tags:
            continue
        raw = _WEB_PREFIX.sub("", (chunk.content or "").split("\n", 1)[0])
        text = " ".join(raw.split())
        if text:
            out.append((text, extract_domain(chunk.source_id or ""), "reverse" in tags, chunk.title or ""))
    return out


def _domains(items: list[str]) -> str:
    return ", ".join(dict.fromkeys(d for d in items if d))


def _transport_lines(origin: str | None, dest: str, knowledge: KnowledgeResult, *, lang: str) -> tuple[list[str], bool]:
    """Bullets built only from phase="transport" snippets; returns (lines, fare_found)."""
    en = lang == "en"
    items = _web_chunks(knowledge, "transport")
    if not items:
        # Evidence merged without phase tags (older cache entries / non-route research).
        items = [(t, d, False, "") for t, d in _web_points(knowledge, limit=4, keep=_TRANSPORT, mentions=dest)]
        if origin:
            items = [i for i in items if _fold(origin) in _fold(i[0])]
    facts = extract_transport_facts(
        [(text, f"{domain} ({'reverse direction' if en else 'sens inverse'})" if rev else domain, title)
         for text, domain, rev, title in items],
        origin=origin,
        dest=dest,
    )
    lines: list[str] = []
    if facts.modes:
        modes = ", ".join(facts.modes)
        doms = _domains([d for ds in facts.modes.values() for d in ds])
        lines.append(f"{'Transport modes mentioned' if en else 'Moyens de transport mentionnés'} : {modes} ({doms}).")
    if facts.durations:
        values = sorted({m for m, _ in facts.durations})
        doms = _domains([d for _, d in facts.durations])
        lo, hi = format_duration(values[0]), format_duration(values[-1])
        if values[-1] - values[0] > 30:
            lines.append(
                f"Duration: the sources give between about {lo} and {hi} depending on the route, mode and connections ({doms})."
                if en
                else f"Durée : les sources consultées indiquent entre environ {lo} et {hi} selon l’itinéraire, le mode et les correspondances ({doms})."
            )
        else:
            lines.append(f"Duration: about {lo} according to {doms}." if en else f"Durée : environ {lo} selon {doms}.")
    if facts.distances:
        kms = sorted({k for k, _ in facts.distances})
        doms = _domains([d for _, d in facts.distances])
        fmt = lambda k: f"{k:g}".replace(".", "," if not en else ".")  # noqa: E731
        dist = fmt(kms[0]) if len(kms) == 1 else f"{fmt(kms[0])}–{fmt(kms[-1])}"
        lines.append(f"Distance: about {dist} km according to {doms}." if en else f"Distance : environ {dist} km selon {doms}.")
    for amount, currency, domain, minimum in facts.prices[:3]:
        qualifier = ("from" if en else "à partir de") if minimum else ("about" if en else "environ")
        if currency == "FCFA":
            lines.append(
                f"Fare: according to {domain}, {qualifier} {amount} FCFA (to be confirmed)."
                if en
                else f"Tarif : selon {domain}, {qualifier} {amount} FCFA (à confirmer)."
            )
        else:
            lines.append(
                f"Fare: according to {domain}, {qualifier} {amount} {currency}. Local fares may differ (no official FCFA fare found)."
                if en
                else f"Tarif : selon {domain}, {qualifier} {amount} {currency}. Les tarifs locaux peuvent différer (aucun tarif officiel en FCFA trouvé)."
            )
    for sentence, domain in facts.connections[:2]:
        lines.append(f"{'Connection' if en else 'Correspondance'} : {'according to' if en else 'selon'} {domain}, « {sentence} »")
    for sentence, domain in facts.departures[:2]:
        lines.append(
            f"{'Departure / agencies' if en else 'Point de départ / agences'} : {'according to' if en else 'selon'} {domain}, « {sentence} »"
        )
    if not lines:
        lines = [
            f"{'According to' if en else 'Selon'} {domain} : {text[:220]}" for text, domain, _, _ in items[:3]
        ]
    return lines, bool(facts.prices)


def _route_section(intent: IntentResult, knowledge: KnowledgeResult, *, lang: str) -> tuple[str, set[str]]:
    dest = intent.destination or ""
    origin = intent.origin
    en = lang == "en"
    lines, fare_found = _transport_lines(origin, dest, knowledge, lang=lang)
    if en:
        title = f"🚍 GETTING FROM {origin.upper()} TO {dest.upper()}" if origin else f"🚍 GETTING TO {dest.upper()}"
        lead = "Information found on the web:"
        missing = (
            f"I couldn't find a reliable web source describing the {origin} → {dest} journey."
            if origin
            else f"I couldn't find reliable transport information online to reach {dest}."
        )
        confirm = ["⚠️ To be confirmed"]
        if not fare_found:
            confirm.append("- I couldn't find a sufficiently reliable current fare online. Please confirm with the agency before leaving.")
        confirm.append("- Fares, timetables, availability and departures can change: check with the travel agency before you go.")
    else:
        title = f"🚍 ALLER DE {origin.upper()} À {dest.upper()}" if origin else f"🚍 ALLER À {dest.upper()}"
        lead = "Informations trouvées sur le Web :"
        missing = (
            f"Je n’ai pas trouvé de source Web fiable décrivant précisément le trajet {origin} → {dest}."
            if origin
            else f"Je n’ai pas trouvé d’information de transport fiable en ligne pour rejoindre {dest}."
        )
        confirm = ["⚠️ Informations à confirmer"]
        if not fare_found:
            confirm.append(
                "- Je n’ai pas trouvé de tarif actuel suffisamment fiable en ligne. "
                "Il est préférable de confirmer auprès de l’agence avant le départ."
            )
        confirm.append(
            "- Prix, horaires, disponibilité et départs peuvent changer : "
            "confirmez-les auprès de l’agence de voyage avant de partir."
        )
    body = f"{lead}\n" + "\n".join(f"- {line}" for line in lines) if lines else missing
    return f"### {title}\n{body}\n\n" + "\n".join(confirm), set()


def route_brief(intent: IntentResult, knowledge: KnowledgeResult, *, lang: str) -> str | None:
    """Deterministic route draft handed to Agent 4 so figures, currencies and sources
    survive the LLM rewrite unchanged."""
    if not intent.destination or intent.intent not in {"TRAVEL_ROUTE", "ITINERARY", "BUDGET_TRIP"}:
        return None
    if intent.intent == "TRAVEL_ROUTE":
        return _render_travel_route(intent, knowledge, lang=lang, voice=False)
    return _route_section(intent, knowledge, lang=lang)[0]


def _render_travel_route(
    intent: IntentResult, knowledge: KnowledgeResult, *, lang: str, voice: bool
) -> str:
    en = lang == "en"
    dest = intent.destination or ""
    origin = intent.origin
    section, _ = _route_section(intent, knowledge, lang=lang)
    parts = [section]
    kb_names = [p.name for p in knowledge.places if (p.city or "").casefold() == dest.casefold()][:5]
    web_dest = [(t, d) for t, d, _, _ in _web_chunks(knowledge, "destination")][:3]
    if intent.wants_activities or intent.duration_days:
        title = f"### 🏛️ WHAT TO DO IN {dest.upper()}" if en else f"### 🏛️ QUE FAIRE À {dest.upper()}"
        lines: list[str] = []
        if kb_names:
            lines.append(
                ("📍 Places listed in SmartMboa:" if en else "📍 Lieux référencés dans SmartMboa :")
                + "\n"
                + "\n".join(f"- {n}" for n in kb_names)
            )
        if web_dest:
            clipped = [(t if len(t) <= 240 else t[:239].rsplit(" ", 1)[0] + "…", d) for t, d in web_dest]
            lines.append(("🌐 Results found on the web:" if en else "🌐 Résultats trouvés sur le Web :") + "\n" + _bullets(clipped))
        if not lines:
            lines.append(
                f"I couldn't find activities in {dest} in SmartMboa or in the web sources consulted."
                if en
                else f"Je n’ai trouvé aucune activité à {dest} dans SmartMboa ni dans les sources Web consultées."
            )
        parts.append(title + "\n" + "\n\n".join(lines))
    text = "\n\n".join(parts)
    # Map and source list are rendered by the client from `map` / `ui_sources`;
    # repeating them here showed each block twice.
    return " ".join(text.replace("###", "").split())[:500] if voice else text


def _dish_kb_notes(knowledge: KnowledgeResult, dish: str, *, limit: int) -> list[str]:
    """KB lines that name the dish (a table row / bullet, not the whole chunk)."""
    key = _fold(dish.split()[0]) if dish else ""
    pattern = re.compile(rf"\b{re.escape(key)}\b") if key else None
    notes: list[str] = []
    for chunk in knowledge.knowledge:
        if (chunk.chunk_id or "").startswith("web:") or not chunk.content:
            continue
        title = (chunk.title or "").strip()
        if pattern and pattern.search(_fold(title)):
            line = f"{title} : {_first_section(chunk.content, limit=220)}"
        else:
            lines = [
                ln for ln in re.split(r"\n|(?<=\|)\s*\|\s*(?=\|)|\s-\s(?=\*\*)", chunk.content)
                if pattern is None or pattern.search(_fold(ln))
            ]
            if not lines:
                continue
            line = " ".join(lines[0].replace("|", " ").replace("**", "").split()).lstrip("- ")
        if line and line not in notes:
            notes.append(line[:240])
        if len(notes) >= limit:
            break
    return notes


def _render_dish(
    intent: IntentResult, knowledge: KnowledgeResult, *, lang: str, voice: bool
) -> str:
    dish = intent.dish or ""
    web = _web_points(knowledge, limit=3)
    kb = _dish_kb_notes(knowledge, dish, limit=2)
    parts: list[str] = []
    if web:
        parts.append(
            (f"{dish} — what the web sources I consulted say:" if lang == "en"
             else f"{dish} — ce que disent les sources web consultées :")
            + "\n" + _bullets(web)
        )
    if kb:
        parts.append(
            ("From the SmartMboa knowledge base:" if lang == "en" else "Complément de la base SmartMboa :")
            + "\n" + "\n".join(f"- {n}" for n in kb)
        )
    if not parts:
        return (
            f"I couldn't find reliable information about {dish}."
            if lang == "en"
            else f"Je n’ai pas trouvé d’information fiable sur le {dish}."
        )
    if intent.wants_images and "images" not in knowledge.missing_information:
        parts.append("Photos found online are shown below." if lang == "en" else "Des photos trouvées en ligne sont affichées ci-dessous.")
    elif intent.wants_images:
        parts.append("I couldn't find photos online." if lang == "en" else "Je n’ai pas trouvé de photos en ligne.")
    text = "\n\n".join(parts)
    return " ".join(text.split())[:500] if voice else text


def _render_restaurants(
    intent: IntentResult, knowledge: KnowledgeResult, *, lang: str, voice: bool
) -> str:
    where = intent.city or intent.region or ("Cameroon" if lang == "en" else "Cameroun")
    dish = intent.dish
    what = f"{dish} " if dish else ""
    web = _web_points(knowledge, limit=4, keep=_RESTAURANT_TERMS, mentions=intent.city)
    if lang == "en":
        head = f"Where to eat {what}in {where} — leads found online (unverified, check before you go):"
        none = f"I couldn't find a reliable restaurant {('serving ' + dish + ' ') if dish else ''}in {where} online."
    else:
        head = f"Où manger {('du ' + dish + ' ') if dish else ''}à {where} — pistes trouvées en ligne (non vérifiées, à confirmer avant d’y aller) :"
        none = f"Je n’ai pas trouvé en ligne de restaurant fiable {('servant du ' + dish + ' ') if dish else ''}à {where}."
    parts = [f"{head}\n{_bullets(web)}" if web else none]
    kb = _dish_kb_notes(knowledge, dish, limit=1) if dish else []
    if kb:
        parts.append(("About the dish: " if lang == "en" else "À propos du plat : ") + kb[0])
    text = "\n\n".join(parts)
    return " ".join(text.split())[:500] if voice else text


def _render_image_search(
    intent: IntentResult, knowledge: KnowledgeResult, *, lang: str, voice: bool
) -> str:
    subject = intent.image_subject or intent.city or intent.location or intent.region or ""
    found = "images" not in knowledge.missing_information
    # « palais de Foumban » — a common noun cannot follow « photos de ».
    quoted = bool(intent.image_subject and intent.image_subject[:1].islower())
    if lang == "en":
        about = f"for « {subject} »" if quoted else f"of {subject}"
        head = (
            f"Here are photos {about} found online (sources under each image)."
            if found
            else f"I couldn't find photos {about} online."
        )
    else:
        about = f"pour « {subject} »" if quoted else f"de {subject}"
        head = (
            f"Voici des photos {about} trouvées en ligne (source sous chaque image)."
            if found
            else f"Je n’ai pas trouvé de photos {about} en ligne."
        )
    kb = [c for c in knowledge.knowledge if c.content and not (c.chunk_id or "").startswith("web:")]
    if kb and not voice:
        content = kb[0].content
        match = _SITE_DESCRIPTION[lang].search(content)
        note = match.group(1) if match else content
        name = (kb[0].title or "").strip()
        body = _first_section(note, limit=260)
        return f"{head}\n\n{name} : {body}" if match and name else f"{head}\n\n{body}"
    return head


_SITE_DESCRIPTION = {
    "fr": re.compile(r"\bFR\s*:\s*(.+?)(?:\s+EN\s*:|$)", re.DOTALL),
    "en": re.compile(r"\bEN\s*:\s*(.+?)(?:\s+FR\s*:|$)", re.DOTALL),
}
