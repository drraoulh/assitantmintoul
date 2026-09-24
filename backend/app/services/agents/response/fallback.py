"""Deterministic text renderer from TourismPlan / KnowledgeResult (no LLM)."""

from __future__ import annotations

from app.services.agents.intent.models import IntentResult
from app.services.agents.knowledge.models import KnowledgeResult
from app.services.agents.planner.models import TourismPlan


def render_deterministic(
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

    if intent.intent == "CLARIFICATION" or intent.confidence < 0.6:
        return _clarification(intent, lang)

    if intent.intent == "BOOKING":
        return _booking_unavailable(lang, has_places=bool(knowledge.places))

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
        return _render_plan(tourism_plan, knowledge, lang=lang, voice=voice)

    if intent.intent == "PLACE_DETAILS" and knowledge.places:
        return _render_place_details(knowledge.places[0], lang=lang, voice=voice)

    if knowledge.places:
        return _render_place_list(knowledge, intent, lang=lang, voice=voice)

    if knowledge.knowledge:
        return _render_knowledge(knowledge, lang=lang, voice=voice)

    return _insufficient(lang)


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
    names = [p.name for p in knowledge.places[:8]]
    if not names:
        return _insufficient(lang)
    if voice:
        joined = ", ".join(names)
        if lang == "en":
            where = f" in {intent.city}" if intent.city else ""
            return f"Verified options{where} include: {joined}."
        where = f" à {intent.city}" if intent.city else ""
        return f"Parmi les options vérifiées{where} : {joined}."
    header = (
        f"Verified places" + (f" in {intent.city}" if intent.city else "") + ":"
        if lang == "en"
        else "Lieux vérifiés" + (f" à {intent.city}" if intent.city else "") + " :"
    )
    lines = [header] + [f"- {n}" for n in names]
    missing = _missing_sentence(knowledge.missing_information, lang)
    if missing:
        lines.append(missing)
    return "\n".join(lines)


def _render_knowledge(knowledge: KnowledgeResult, *, lang: str, voice: bool) -> str:
    chunks = [c.content.strip() for c in knowledge.knowledge if c.content][:3]
    if not chunks:
        return _insufficient(lang)
    body = " ".join(chunks)
    if voice:
        return " ".join(body.split())[:500]
    title = "From verified notes:" if lang == "en" else "D’après les notes vérifiées :"
    return f"{title}\n{body}"
