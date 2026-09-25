"""General factual questions about Cameroon (who / what / when / how many).

Stable facts are answered from this curated table. Volatile ones (office
holders, population, results) are only detected here: the router forces a web
search for them so the answer never comes from stale data.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.services.agents.intent.extractors import fold

_SOURCE = "Constitution du Cameroun (1996) / sources officielles"

_VOLATILE = re.compile(
    r"\b(?:president|presidente|presidency|chef\s+de\s+l['’ ]?etat|head\s+of\s+state|"
    r"premier\s+ministre|prime\s+minister|ministres?|minister|gouvernement|government|"
    r"population|habitants?|people\s+live|inhabitants|"
    r"elections?|elu|elected|actuel(?:le)?s?|current(?:ly)?|"
    r"qui\s+a\s+gagne|who\s+won|vainqueur|winner|score|classement|ranking|"
    r"taux\s+de\s+change|exchange\s+rate|pib|gdp)\b"
)

_STABLE_TOPICS = re.compile(
    r"\b(?:langues?|languages?|parle[- ]t[- ]on|spoken|"
    r"independan\w*|independence|reunification|"
    r"fete\s+nationale|national\s+day|20\s+mai|"
    r"devise|motto|hymne|anthem|drapeau|flag|"
    r"superficie|area|taille\s+du\s+pays|"
    r"indicatif|dialling\s+code|calling\s+code|country\s+code|"
    r"fuseau\s+horaire|time\s*zone|heure\s+(?:locale|au\s+cameroun)|"
    r"monnaie|currency|devise\s+monetaire|"
    r"plus\s+grande\s+ville|largest\s+city|biggest\s+city|"
    r"combien\s+de\s+regions|how\s+many\s+regions|"
    r"constitution|religions?)\b"
)

_QUESTION = re.compile(
    r"\?|^\s*(?:qui|quel(?:le)?s?|quand|combien|comment|pourquoi|ou|que|quoi|"
    r"who|what|when|how|which|where|why|est[- ]ce|c['’ ]?est\s+(?:qui|quoi|quand|combien))\b"
    r"|\bc['’ ]?est\s+(?:qui|quoi|quand|combien)\b"
)

_NATIONAL = re.compile(r"\b(?:cameroun\w*|cameroon\w*|pays|country|national\w*)\b")


@dataclass(frozen=True)
class NationalFact:
    key: str
    pattern: re.Pattern[str]
    text_fr: str
    text_en: str


NATIONAL_FACTS: tuple[NationalFact, ...] = (
    NationalFact(
        "official_languages",
        re.compile(r"\b(?:langues?|languages?|parle[- ]t[- ]on|spoken)\b"),
        "Le Cameroun a deux langues officielles, le français et l’anglais, "
        "et compte plus de 250 langues nationales (ewondo, douala, fulfulde, bassa…).",
        "Cameroon has two official languages, French and English, "
        "and more than 250 national languages (Ewondo, Duala, Fulfulde, Bassa…).",
    ),
    NationalFact(
        "independence",
        re.compile(r"\b(?:independan\w*|independence|reunification)\b"),
        "Le Cameroun sous tutelle française est devenu indépendant le 1er janvier 1960 ; "
        "la réunification avec le Southern Cameroons a eu lieu le 1er octobre 1961.",
        "French-administered Cameroon became independent on 1 January 1960; "
        "reunification with Southern Cameroons followed on 1 October 1961.",
    ),
    NationalFact(
        "national_day",
        re.compile(r"\b(?:fete\s+nationale|national\s+day|20\s+mai)\b"),
        "La fête nationale du Cameroun est le 20 mai (fête de l’Unité, "
        "en souvenir du référendum de 1972 instituant l’État unitaire).",
        "Cameroon's National Day is 20 May (Unity Day, commemorating the "
        "1972 referendum that created the unitary state).",
    ),
    NationalFact(
        "motto",
        re.compile(r"\b(?:devise(?!\s+monetaire)|motto)\b"),
        "La devise du Cameroun est « Paix – Travail – Patrie ».",
        "Cameroon's motto is \"Peace – Work – Fatherland\".",
    ),
    NationalFact(
        "anthem",
        re.compile(r"\b(?:hymne|anthem)\b"),
        "L’hymne national du Cameroun est « Ô Cameroun, berceau de nos ancêtres ».",
        "Cameroon's national anthem is \"O Cameroon, Cradle of our Forefathers\".",
    ),
    NationalFact(
        "flag",
        re.compile(r"\b(?:drapeau|flag)\b"),
        "Le drapeau du Cameroun a trois bandes verticales vert, rouge et jaune, "
        "avec une étoile jaune à cinq branches au centre de la bande rouge.",
        "Cameroon's flag has three vertical stripes — green, red and yellow — "
        "with a five-pointed yellow star in the centre of the red stripe.",
    ),
    NationalFact(
        "area",
        re.compile(r"\b(?:superficie|area|taille\s+du\s+pays)\b"),
        "Le Cameroun couvre environ 475 440 km².",
        "Cameroon covers about 475,440 km².",
    ),
    NationalFact(
        "calling_code",
        re.compile(r"\b(?:indicatif|dialling\s+code|calling\s+code|country\s+code)\b"),
        "L’indicatif téléphonique du Cameroun est le +237.",
        "Cameroon's international dialling code is +237.",
    ),
    NationalFact(
        "time_zone",
        re.compile(r"\b(?:fuseau\s+horaire|time\s*zone|heure\s+(?:locale|au\s+cameroun))\b"),
        "Le Cameroun est à l’heure d’Afrique de l’Ouest (UTC+1), sans heure d’été.",
        "Cameroon is on West Africa Time (UTC+1), with no daylight saving.",
    ),
    NationalFact(
        "currency",
        re.compile(r"\b(?:monnaie|currency|devise\s+monetaire)\b"),
        "La monnaie du Cameroun est le franc CFA (XAF), émis par la BEAC.",
        "Cameroon's currency is the Central African CFA franc (XAF), issued by the BEAC.",
    ),
    NationalFact(
        "largest_city",
        re.compile(r"\b(?:plus\s+grande\s+ville|largest\s+city|biggest\s+city)\b"),
        "Douala est la plus grande ville et la capitale économique du Cameroun ; "
        "Yaoundé en est la capitale politique.",
        "Douala is Cameroon's largest city and economic capital; "
        "Yaoundé is the political capital.",
    ),
    NationalFact(
        "regions",
        re.compile(r"\b(?:combien\s+de\s+regions|how\s+many\s+regions)\b"),
        "Le Cameroun compte 10 régions : Adamaoua, Centre, Est, Extrême-Nord, Littoral, "
        "Nord, Nord-Ouest, Ouest, Sud et Sud-Ouest.",
        "Cameroon has 10 regions: Adamawa, Centre, East, Far North, Littoral, "
        "North, North-West, West, South and South-West.",
    ),
)


def is_volatile_fact_query(query: str) -> bool:
    q = fold(query or "")
    return bool(_VOLATILE.search(q)) and bool(_QUESTION.search(q))


def is_general_fact_query(query: str) -> bool:
    """A who/what/when question about Cameroon itself, not a trip request."""
    q = fold(query or "")
    if not _QUESTION.search(q):
        return False
    if _VOLATILE.search(q):
        return bool(_NATIONAL.search(q)) or bool(re.search(r"\bqui\s+a\s+gagne|who\s+won\b", q))
    return bool(_STABLE_TOPICS.search(q)) and bool(_NATIONAL.search(q))


def answer_national_fact(query: str) -> NationalFact | None:
    q = fold(query or "")
    if not _NATIONAL.search(q) or _VOLATILE.search(q):
        return None
    for fact in NATIONAL_FACTS:
        if fact.pattern.search(q):
            return fact
    return None


NATIONAL_FACTS_SOURCE = _SOURCE
