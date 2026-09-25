"""Slot extraction — never invent values that are not explicit in the text."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field


def fold(text: str) -> str:
    lowered = (text or "").casefold().strip()
    decomposed = unicodedata.normalize("NFKD", lowered)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


# Known Cameroon cities (folded → display). Only extract if explicitly present.
_CITIES: dict[str, str] = {
    "yaounde": "Yaoundé",
    "douala": "Douala",
    "kribi": "Kribi",
    "limbe": "Limbé",
    "buea": "Buea",
    "bafoussam": "Bafoussam",
    "bamenda": "Bamenda",
    "garoua": "Garoua",
    "maroua": "Maroua",
    "ngaoundere": "Ngaoundéré",
    "ebolowa": "Ebolowa",
    "bertoua": "Bertoua",
    "dschang": "Dschang",
    "foumban": "Foumban",
    "mbouda": "Mbouda",
    "bafang": "Bafang",
    "baham": "Baham",
    "bandjoun": "Bandjoun",
    "bangangte": "Bangangté",
    "batcham": "Batcham",
    "bana": "Bana",
    "penka-michel": "Penka-Michel",
    "penka michel": "Penka-Michel",
    "batoufam": "Batoufam",
    "foumbot": "Foumbot",
    "santchou": "Santchou",
    "edea": "Edéa",
    "nkongsamba": "Nkongsamba",
    "melong": "Melong",
    "yabassi": "Yabassi",
    "mouanko": "Mouanko",
    "mbalmayo": "Mbalmayo",
    "mfou": "Mfou",
    "soa": "Soa",
    "monatele": "Monatélé",
    "campo": "Campo",
    "sangmelima": "Sangmélima",
    "ambam": "Ambam",
    "kumba": "Kumba",
    "mundemba": "Mundemba",
    "tiko": "Tiko",
    "mamfe": "Mamfe",
    "idenau": "Idenau",
    "bafut": "Bafut",
    "oku": "Oku",
    "kumbo": "Kumbo",
    "wum": "Wum",
    "fundong": "Fundong",
    "nkambe": "Nkambe",
    "mbengwi": "Mbengwi",
    "ndop": "Ndop",
    "waza": "Waza",
    "rhumsiki": "Rhumsiki",
    "roumsiki": "Rhumsiki",
    "maga": "Maga",
    "mora": "Mora",
    "yagoua": "Yagoua",
    "kousseri": "Kousséri",
    "kaele": "Kaélé",
    "banyo": "Banyo",
    "meiganga": "Meiganga",
    "tibati": "Tibati",
    "tignere": "Tignère",
    "figuil": "Figuil",
    "tchollire": "Tcholliré",
    "guider": "Guider",
    "poli": "Poli",
    "touboro": "Touboro",
    "batouri": "Batouri",
    "abong-mbang": "Abong-Mbang",
    "abong mbang": "Abong-Mbang",
    "yokadouma": "Yokadouma",
    "moloundou": "Moloundou",
    "somalomo": "Somalomo",
}

_REGIONS: dict[str, str] = {
    "centre": "Centre",
    "littoral": "Littoral",
    "ouest": "Ouest",
    "west": "Ouest",
    "west region": "Ouest",
    "sud-ouest": "Sud-Ouest",
    "sud ouest": "Sud-Ouest",
    "south-west": "Sud-Ouest",
    "southwest": "Sud-Ouest",
    "nord-ouest": "Nord-Ouest",
    "nord ouest": "Nord-Ouest",
    "north-west": "Nord-Ouest",
    "northwest": "Nord-Ouest",
    "extreme-nord": "Extrême-Nord",
    "extreme nord": "Extrême-Nord",
    "extrême-nord": "Extrême-Nord",
    "extrême nord": "Extrême-Nord",
    "far north": "Extrême-Nord",
    "far-north": "Extrême-Nord",
    "adamaoua": "Adamaoua",
    "adamawa": "Adamaoua",
    "sud": "Sud",
    "south": "Sud",
    "nord": "Nord",
    "north": "Nord",
    "est": "Est",
    "east": "Est",
}

# Bare "est" is also the French verb — never match it with a plain substring.
# Bare "centre" can mean "city centre" — require regional cues.
_REGION_SAFE_SUBSTRING = {
    "est": re.compile(
        r"(?:\bl['’]est\b|\br[eé]gion\s+(?:de\s+l['’])?est\b|\beast(?:\s+region)?\b|"
        r"\bdans\s+l['’]est\b|\bvers\s+l['’]est\b)",
        re.IGNORECASE,
    ),
    "centre": re.compile(
        r"(?:\br[eé]gion\s+(?:du\s+)?centre\b|\bcentre\s+(?:du\s+)?cameroun\b|"
        r"\bdans\s+le\s+centre\b|\bau\s+centre\s+(?:du\s+)?cameroun\b|"
        # "du/au/le centre" as region when not city-centre / centre touristique / faunique
        r"\b(?:du|au|le)\s+centre\b(?!\s+(?:ville|ville|faunique|touristique|commercial|culturel))|"
        r"\bcenter\s+region\b|\bcentral\s+region\b)",
        re.IGNORECASE,
    ),
    "sud": re.compile(
        r"(?:\br[eé]gion\s+(?:du\s+)?sud\b|\bsud\s+(?:du\s+)?cameroun\b|"
        r"\bdans\s+le\s+sud\b|\bau\s+sud\s+(?:du\s+)?cameroun\b|"
        r"\bsouth\s+region\b|\bsouth\s+cameroon\b)",
        re.IGNORECASE,
    ),
    "nord": re.compile(
        r"(?:\br[eé]gion\s+(?:du\s+)?nord(?![- ]?ouest)\b|"
        r"\bnord(?![- ]?ouest)\s+(?:du\s+)?cameroun\b|"
        r"\bdans\s+le\s+nord(?![- ]?ouest)\b|"
        r"\bau\s+nord(?![- ]?ouest)\s+(?:du\s+)?cameroun\b|"
        r"\bvisiter\s+le\s+nord(?![- ]?ouest)\b|"
        r"\bnorth(?![- ]?west)\s+region\b|"
        r"\bnorth(?![- ]?west)\s+cameroon\b)",
        re.IGNORECASE,
    ),
    "north": re.compile(
        r"(?:\bnorth(?![- ]?west)\s+region\b|"
        r"\bnorth(?![- ]?west)\s+cameroon\b|"
        r"\bregion\s+of\s+the\s+north(?![- ]?west)\b|"
        r"\bvisit\s+(?:the\s+)?north(?![- ]?west)\b)",
        re.IGNORECASE,
    ),
}

# Topic word followed by a bare region name: « plat traditionnel centre », « cuisine du sud ».
_TOPIC_REGION_LABELS = {
    "centre": "Centre",
    "sud": "Sud",
    "nord": "Nord",
    "est": "Est",
    "ouest": "Ouest",
    "littoral": "Littoral",
    "adamaoua": "Adamaoua",
    "sud-ouest": "Sud-Ouest",
    "nord-ouest": "Nord-Ouest",
    "extreme-nord": "Extrême-Nord",
}
_TOPIC_REGION = re.compile(
    r"\b(?:plats?|cuisine|nourriture|gastronomie|specialites?|spécialités?|"
    r"traditionnel(?:le)?s?|culture|festivals?|traditions?)\s+"
    r"(?:(?:du|de\s+la\s+r[eé]gion\s+du|de\s+l['’]|de\s+la\s+r[eé]gion\s+de\s+l['’]|au|a\s+l['’]|à\s+l['’])\s*)?"
    r"(?P<region>sud[- ]ouest|nord[- ]ouest|extreme[- ]nord|centre|sud|nord|est|ouest|littoral|adamaoua)\b"
    r"(?!\s+(?:ville|faunique|touristique|commercial|culturel))",
    re.IGNORECASE,
)

# Cultural area cues → region (no city invented).
_OUEST_CULTURE = re.compile(
    r"\b(bamoun|bamum|bamil[eé]k[eé]|grassfields|chefferies?\s+de\s+l['’]?ouest)\b",
    re.IGNORECASE,
)
_LITTORAL_CULTURE = re.compile(
    r"\b(sawa|ndol[eé]|wouri|bonanjo|duala)\b",
    re.IGNORECASE,
)
_CENTRE_CULTURE = re.compile(
    r"\b(ewondo|fang[- ]?beti|mokolo|mefou|ebogo|r[eé]unification)\b",
    re.IGNORECASE,
)
_SUD_CULTURE = re.compile(
    r"\b(lob[eé]|grand\s+batanga|campo[- ]?ma|nkolandom|poisson\s+brais)\b",
    re.IGNORECASE,
)
_SUD_OUEST_CULTURE = re.compile(
    r"\b(eru|okok|korup|barombi|pidgin|sable\s+noir|black\s+sand|"
    r"mont\s+cameroun|mount\s+cameroon|bimbia|down\s+beach)\b",
    re.IGNORECASE,
)
_NORD_OUEST_CULTURE = re.compile(
    r"\b(bafut|oku|kumbo|lamns[oó]'?|nso|lac\s+oku|lac\s+kuk|"
    r"station\s+hill|savanna\s+botanic)\b",
    re.IGNORECASE,
)
_EXTREME_NORD_CULTURE = re.compile(
    r"\b(waza|rhumsiki|roumsiki|kapsiki|mandara|mofou|lac\s+de\s+maga)\b",
    re.IGNORECASE,
)
_ADAMAOUA_CULTURE = re.compile(
    r"\b(lac\s+tison|ngan[- ]?ha|lancrenon|beka[- ]?hoss|"
    r"lamidat\s+de\s+ngaound[eé]r[eé]|palais\s+du\s+lamido)\b",
    re.IGNORECASE,
)
_NORD_CULTURE = re.compile(
    r"\b(benoue|bouba\s*ndjida|lagdo|dirif|iles?\s+aux\s+damans|"
    r"lamidat\s+de\s+demsa|demsa|"
    r"shalom\s+city|ribadou|motel\s+plaza)\b",
    re.IGNORECASE,
)
_EST_CULTURE = re.compile(
    r"\b(lobeke|reserve\s+du\s+dja|parc\s+(?:national\s+)?(?:de\s+)?lobeke|"
    r"village\s+artisanale?\s+de\s+bertoua)\b",
    re.IGNORECASE,
)

# Named places often asked about specifically (PLACE_DETAILS).
_KNOWN_PLACES: dict[str, str] = {
    "mont cameroun": "Mont Cameroun",
    "mont cameroon": "Mont Cameroun",
    "musee national": "Musée National",
    "museum national": "Musée National",
    "monument de la reunification": "Monument de la Réunification",
    "chutes de la lobé": "Chutes de la Lobé",
    "chutes de la lobe": "Chutes de la Lobé",
    "parc de waza": "Parc national de Waza",
    "reserve du dja": "Réserve du Dja",
    "lac tchad": "Lac Tchad",
    "lac baleng": "Lac Baleng",
    "lake baleng": "Lac Baleng",
    "lac mbapit": "Lac Mbapit",
    "lake mbapit": "Lac Mbapit",
    "mont mbapit": "Mont Mbapit",
    "palais royal de foumban": "Palais royal de Foumban",
    "palais des rois bamoun": "Palais royal de Foumban",
    "chefferie de bandjoun": "Chefferie de Bandjoun",
    "chutes de la mouankeu": "Chutes De La Mouankeu",
    "chutes de la metche": "Chutes De La Métché",
    "chutes de la métché": "Chutes De La Métché",
    "haras de balatchi": "Le Haras De Balatchi",
    "falaise de foreke": "La Falaise De Foreke",
    "falaise de foréké": "La Falaise De Foreke",
    "quartier bonanjo": "Quartier Bonanjo (Douala)",
    "bonanjo": "Quartier Bonanjo (Douala)",
    "palais de la culture": "Palais De La Culture Du Peuple Sawa",
    "musee maritime": "Musée Maritime De Douala",
    "musée maritime": "Musée Maritime De Douala",
    "chutes d'ekom": "Chutes d’Ekom-Nkam",
    "chutes d ekom": "Chutes d’Ekom-Nkam",
    "ekom-nkam": "Chutes d’Ekom-Nkam",
    "ekom nkam": "Chutes d’Ekom-Nkam",
    "pont du wouri": "Pont Du Wouri",
    "fleuve wouri": "Fleuve Wouri",
    "ile de manoka": "Ile De Manoka",
    "île de manoka": "Ile De Manoka",
    "monument de la reunification": "Monument de la Réunification",
    "monument de la réunification": "Monument de la Réunification",
    "musee national du cameroun": "Musée national du Cameroun",
    "musée national du cameroun": "Musée national du Cameroun",
    "mont febe": "Mont Fébé",
    "mont fébé": "Mont Fébé",
    "marche mokolo": "Marché Mokolo",
    "marché mokolo": "Marché Mokolo",
    "sanctuaire de mefou": "Sanctuaire de primates de Mefou",
    "sanctuaire de primates de mefou": "Sanctuaire de primates de Mefou",
    "mefou": "Sanctuaire de primates de Mefou",
    "ebogo": "Site Touristique D'ebogo",
    "chutes de la bongola": "Les Chutes De La Bongola",
    "plage de grand batanga": "Plage de Grand Batanga",
    "grand batanga": "Plage de Grand Batanga",
    "parc campo": "Parc national de Campo-Ma'an",
    "campo-ma'an": "Parc national de Campo-Ma'an",
    "campo maan": "Parc national de Campo-Ma'an",
    "rhumsiki": "Rhumsiki",
    "korup": "Korup",
    "parc national de korup": "Parc national de Korup",
    "parc de korup": "Parc national de Korup",
    "jardin botanique de limbe": "Jardin botanique de Limbé",
    "jardin botanique de limbé": "Jardin botanique de Limbé",
    "centre faunique de limbe": "Centre faunique de Limbé",
    "centre faunique de limbé": "Centre faunique de Limbé",
    "limbe wildlife": "Centre faunique de Limbé",
    "down beach": "Down Beach (Limbé)",
    "lac barombi mbo": "Lac Barombi Mbo",
    "barombi mbo": "Lac Barombi Mbo",
    "lac barombi kotto": "Lac Barombi Kotto",
    "barombi kotto": "Lac Barombi Kotto",
    "bimbia": "Bimbia",
    "palais de bafut": "Palais de Bafut",
    "chefferie de bafut": "Palais de Bafut",
    "lac oku": "Lac Oku",
    "lake oku": "Lac Oku",
    "lac kuk": "Lac Kuk",
    "lake kuk": "Lac Kuk",
    "chefferie d'oku": "La Chefferie D'oku",
    "chefferie d oku": "La Chefferie D'oku",
    "savanna botanic": "Savanna Botanic Garden De Bamenda",
    "parc national de waza": "Parc national de Waza",
    "pic kapsiki": "Rhumsiki et pic Kapsiki",
    "monts mandara": "Monts Mandara (depuis Maroua)",
    "lac de maga": "Lac De Maga",
    "gorges de kola": "Les Gorges De Kola",
    "lac tison": "Lac Tison",
    "lake tison": "Lac Tison",
    "palais du lamido": "Palais du Lamido de Ngaoundéré",
    "lamidat de ngaoundere": "Lamidat De Ngaoundéré",
    "lamidat de ngaoundéré": "Lamidat De Ngaoundéré",
    "mont ngan-ha": "Le Mont Ngan-Ha",
    "mont ngan ha": "Le Mont Ngan-Ha",
    "chutes lancrenon": "Chutes Lancrenon",
    "parc de la benoue": "Parc national de la Bénoué",
    "parc de la bénoué": "Parc national de la Bénoué",
    "parc national de la benoue": "Parc national de la Bénoué",
    "parc national de la bénoué": "Parc national de la Bénoué",
    "bouba ndjida": "Parc national de Bouba Ndjida",
    "parc faro": "Parc National Du Faro",
    "fleuve benoue": "Fleuve Bénoué (Garoua)",
    "fleuve bénoué": "Fleuve Bénoué (Garoua)",
    "reserve du dja": "Réserve de faune du Dja",
    "réserve du dja": "Réserve de faune du Dja",
    "parc lobeke": "Parc national de Lobéké",
    "parc de lobeke": "Parc national de Lobéké",
    "parc national de lobeke": "Parc national de Lobéké",
    "parc national de lobéké": "Parc national de Lobéké",
}

_DURATION = re.compile(
    r"\b(?P<n>\d{1,2})\s*(?:jours?|days?|j\.?)\b"
    r"|\b(?:pendant|for|during)\s+(?P<n2>\d{1,2})\s*(?:jours?|days?)\b"
    r"|\b(?:une|1)\s+semaine\b"
    r"|\b(?:a|à|for)\s+(?P<n3>\d{1,2})\s*(?:jours?|days?)\b",
    re.IGNORECASE,
)

_WEEK = re.compile(r"\b(?:une|1|one)\s+semaine\b|\bone\s+week\b", re.IGNORECASE)

_BUDGET = re.compile(
    r"(?P<amount>\d[\d\s.,]{2,})\s*(?:fcfa|xaf|f\s*cfa|francs?(?:\s+cfa)?)"
    r"|(?:budget(?:\s+de)?|avec)\s*(?P<amount2>\d[\d\s.,]{2,})",
    re.IGNORECASE,
)

_PEOPLE = re.compile(
    r"\b(?:nous\s+sommes|we\s+are|famille\s+de|family\s+of|groupe\s+de|"
    r"group\s+of)\s*(?P<n>\d{1,2})\b"
    r"|\b(?P<n2>\d{1,2})\s*(?:personnes?|people|pers\.?|adultes?)\b"
    r"|\bnous\s+sommes\s+(?P<n3>\d{1,2})\b",
    re.IGNORECASE,
)

_CHILDREN = re.compile(
    r"\b(?P<n>\d{1,2})\s*(?:enfants?|children|kids?)\b",
    re.IGNORECASE,
)


@dataclass
class ExtractedSlots:
    location: str | None = None
    region: str | None = None
    city: str | None = None
    duration_days: int | None = None
    budget_xaf: int | None = None
    people: int | None = None
    children: int | None = None
    interests: list[str] = field(default_factory=list)
    travel_style: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    language: str | None = None
    place_name: str | None = None
    origin: str | None = None
    destination: str | None = None
    dish: str | None = None
    wants_images: bool = False
    wants_activities: bool = False
    image_subject: str | None = None
    on_site: bool = False
    return_trip: bool = False


_CITY_ALT = "|".join(re.escape(k) for k in sorted(_CITIES, key=len, reverse=True))
_TRAVEL_CUE = re.compile(
    r"\b(?:aller|vais|va|allons|allez|rendre|rends|trajet|voyage[rz]?|voyageons|transport|"
    r"bus|cars?|taxi|train|vol|avion|route|quitter|quitte|quittant|partir|pars|part|"
    r"arriver|arrive|rejoindre|distance|duree|combien\s+de\s+temps|chemin|"
    r"retourner|retourne|rentrer|rentre|revenir|reviens|retour|"
    r"get|go|going|travel(?:l?ing)?|trip|drive|fly|leave|leaving|reach|journey|return)\b"
)
_RETURN_CUE = re.compile(
    r"\b(?:retourner|retourne|rentrer|rentre|revenir|reviens|retour|return|go\s+back|get\s+back|"
    r"ensuite|apres\s+ca|puis|then|afterwards)\b"
)
_ON_SITE = re.compile(
    r"\b(?:sur\s+place|la[- ]bas|une\s+fois\s+(?:la[- ]bas|arrive\w*|sur\s+place)|"
    r"on\s+site|over\s+there|once\s+(?:there|i\s+arrive))\b"
)
_CURRENT_LOCATION = re.compile(
    r"\b(?:je\s+suis(?:\s+actuellement)?|je\s+me\s+trouve|j['’ ]?habite|je\s+vis|"
    r"nous\s+sommes|on\s+est|i\s+am|i['’ ]?m|we\s+are|we['’ ]?re)\s+(?:a|au|en|in|at)\s+"
    rf"(?P<o>{_CITY_ALT})\b"
)
_ROUTE_PATTERNS = (
    re.compile(
        rf"\b(?:de|d['’ ]|depuis|from|quitter|quitte|quittant|leave|leaving|partir\s+de|pars\s+de|part\s+de)\s*"
        rf"(?P<o>{_CITY_ALT})\b.{{0,40}}?\b(?:a|au|vers|pour|jusqu['’ ]?a|to|towards|for)\s+(?P<d>{_CITY_ALT})\b"
    ),
    re.compile(rf"\bentre\s+(?P<o>{_CITY_ALT})\s+et\s+(?P<d>{_CITY_ALT})\b"),
    re.compile(rf"\bbetween\s+(?P<o>{_CITY_ALT})\s+and\s+(?P<d>{_CITY_ALT})\b"),
    re.compile(rf"\b(?P<o>{_CITY_ALT})\s*(?:->|→|–|—|-)\s*(?P<d>{_CITY_ALT})\b"),
)
_DESTINATION_ONLY = re.compile(
    r"\b(?:aller|vais|allons|me\s+rendre|se\s+rendre|nous\s+rendre|arriver|rejoindre|"
    r"retourner|rentrer|revenir|partir|pars|get|go|travel|getting|return|go\s+back|get\s+back)\s+"
    rf"(?:a|au|en|to|jusqu['’ ]?a|vers|pour)\s+(?P<d>{_CITY_ALT})\b"
)
# "Je veux voir Foumban", "Montre-moi le palais de Foumban" — raw text, keeps accents.
_SEE_SUBJECT = re.compile(
    r"(?:\b(?:je\s+veux|je\s+voudrais|j['’]aimerais|on\s+peut|puis[- ]je|i\s+want\s+to|"
    r"i['’]d\s+like\s+to|can\s+i|let\s+me)\s+(?:voir|see)|\bmontre[sz]?[- ]moi|\bshow\s+me)\s+"
    r"(?P<s>[^?!.]{2,80})",
    re.IGNORECASE,
)
_SEE_EXCLUDE = re.compile(
    r"\b(?:hotels?|hebergement\w*|restaurants?|manger|itineraire|trajet|route|programme|"
    r"lieux|sites|activites?|carte|map|prix|tarifs?|comment|que|quoi|visiter|faire)\b"
)
_LEADING_ARTICLE = re.compile(
    r"^(?:(?:des|les|quelques|some|the)?\s*(?:photos?|images?|pictures?|pics)\s+(?:de\s+la|de\s+l['’]|du|des|de|d['’]|of(?:\s+the)?)\s*)?"
    r"(?:le|la|les|l['’]|du|des|un|une|the|a)?\s*",
    re.IGNORECASE,
)
_ACTIVITIES = re.compile(
    r"\b(?:que\s+faire|quoi\s+faire|que\s+visiter|quoi\s+visiter|a\s+voir|activites?|"
    r"visiter|conseill\w*|recommand\w*|programme|things\s+to\s+do|what\s+to\s+do|"
    r"what\s+to\s+see|activities|suggest\w*)\b"
)
_IMAGE_REQUEST = re.compile(
    r"\b(?:photos?|images?|pictures?|pics|galerie|a\s+quoi\s+ressembl\w+|looks?\s+like|"
    r"montre[sz]?[- ]moi\s+(?:a\s+quoi|comment))\b"
)
_SEE_WORD = re.compile(r"\b(?:voir|see|montre[sz]?[- ]moi|show\s+me)\b")

# Cameroonian dishes (folded → display).
_DISHES: dict[str, str] = {
    "eru": "Eru",
    "ndole": "Ndolé",
    "achu": "Achu",
    "koki": "Koki",
    "okok": "Okok",
    "poulet dg": "Poulet DG",
    "mbongo tchobi": "Mbongo Tchobi",
    "mbongo": "Mbongo Tchobi",
    "sanga": "Sanga",
    "kpem": "Kpem",
    "kwem": "Kwem",
    "sauce jaune": "Achu (sauce jaune)",
    "bobolo": "Bobolo",
    "miondo": "Miondo",
    "soya": "Soya",
    "kondre": "Kondrè",
    "nkui": "Nkui",
    "folere": "Folléré",
    "ekwang": "Ekwang",
    "corn chaff": "Corn chaff",
    "water fufu": "Water fufu",
    "fufu": "Fufu",
    "koki beans": "Koki",
    "pepper soup": "Pepper soup",
    "mintumba": "Mintumba",
    "ndomba": "Ndomba",
    "nnam ngon": "Nnam ngon",
    "taro": "Taro",
    "poisson braise": "Poisson braisé",
    "puff puff": "Puff-puff",
    "beignets haricots": "Beignets-haricots",
    "mbanga soup": "Mbanga soup",
    "kati kati": "Kati kati",
}


def mentioned_towns(text: str) -> set[str]:
    """Display names of the Cameroonian towns named in ``text`` (accent-insensitive)."""
    folded = fold(text)
    return {label for key, label in _CITIES.items() if re.search(rf"\b{re.escape(key)}\b", folded)}


def _extract_route(folded: str) -> tuple[str | None, str | None]:
    if not _TRAVEL_CUE.search(folded):
        return None, None
    for pattern in _ROUTE_PATTERNS:
        for match in pattern.finditer(folded):
            origin, dest = _CITIES[match.group("o")], _CITIES[match.group("d")]
            if origin != dest:
                return origin, dest
    match = _DESTINATION_ONLY.search(folded)
    if match:
        dest = _CITIES[match.group("d")]
        here = _CURRENT_LOCATION.search(folded)
        origin = _CITIES[here.group("o")] if here else None
        return (origin if origin != dest else None), dest
    return None, None


def _extract_image_subject(raw: str) -> str | None:
    match = _SEE_SUBJECT.search(raw)
    if not match:
        return None
    subject = match.group("s").strip(" ,;:")
    if _SEE_EXCLUDE.search(fold(subject)):
        return None
    subject = _LEADING_ARTICLE.sub("", subject).strip()
    folded = fold(subject)
    if not any(re.search(rf"\b{re.escape(k)}\b", folded) for k in _CITIES) and not any(
        k in folded for k in _KNOWN_PLACES
    ):
        return None
    return subject[:80] or None


def _extract_dish(folded: str) -> str | None:
    for key in sorted(_DISHES, key=len, reverse=True):
        if re.search(rf"\b{re.escape(key)}\b", folded):
            return _DISHES[key]
    return None


def _parse_int_amount(raw: str) -> int | None:
    digits = re.sub(r"[^\d]", "", raw or "")
    if not digits:
        return None
    try:
        value = int(digits)
    except ValueError:
        return None
    # Ignore tiny numbers that are clearly not budgets (e.g. "3 jours").
    if value < 1000:
        return None
    return value


def extract_slots(message: str, *, locale: str | None = None) -> ExtractedSlots:
    """Extract only explicitly stated parameters. Missing → None / []."""
    raw = (message or "").strip()
    folded = fold(raw)
    slots = ExtractedSlots()
    if locale in {"fr", "en"}:
        slots.language = locale

    for key, label in sorted(_CITIES.items(), key=lambda kv: len(kv[0]), reverse=True):
        if re.search(rf"\b{re.escape(key)}\b", folded):
            slots.city = label
            slots.location = label
            break

    for key, label in sorted(_REGIONS.items(), key=lambda kv: len(kv[0]), reverse=True):
        safe = _REGION_SAFE_SUBSTRING.get(key)
        if safe is not None:
            if not safe.search(folded):
                continue
        elif key not in folded:
            continue
        slots.region = label
        if slots.location is None:
            slots.location = label
        break

    if slots.region is None:
        topic_region = _TOPIC_REGION.search(folded)
        if topic_region:
            label = _TOPIC_REGION_LABELS[topic_region.group("region").replace(" ", "-")]
            slots.region = label
            if slots.location is None:
                slots.location = label

    if slots.region is None and _OUEST_CULTURE.search(folded):
        slots.region = "Ouest"
        if slots.location is None:
            slots.location = "Ouest"

    if slots.region is None and _LITTORAL_CULTURE.search(folded):
        slots.region = "Littoral"
        if slots.location is None:
            slots.location = "Littoral"

    if slots.region is None and _CENTRE_CULTURE.search(folded):
        slots.region = "Centre"
        if slots.location is None:
            slots.location = "Centre"

    if slots.region is None and _SUD_CULTURE.search(folded):
        slots.region = "Sud"
        if slots.location is None:
            slots.location = "Sud"

    if slots.region is None and _SUD_OUEST_CULTURE.search(folded):
        slots.region = "Sud-Ouest"
        if slots.location is None:
            slots.location = "Sud-Ouest"

    if slots.region is None and _NORD_OUEST_CULTURE.search(folded):
        slots.region = "Nord-Ouest"
        if slots.location is None:
            slots.location = "Nord-Ouest"

    if slots.region is None and _EXTREME_NORD_CULTURE.search(folded):
        slots.region = "Extrême-Nord"
        if slots.location is None:
            slots.location = "Extrême-Nord"

    if slots.region is None and _ADAMAOUA_CULTURE.search(folded):
        slots.region = "Adamaoua"
        if slots.location is None:
            slots.location = "Adamaoua"

    if slots.region is None and _NORD_CULTURE.search(folded):
        slots.region = "Nord"
        if slots.location is None:
            slots.location = "Nord"

    if slots.region is None and _EST_CULTURE.search(folded):
        slots.region = "Est"
        if slots.location is None:
            slots.location = "Est"

    for key, label in sorted(_KNOWN_PLACES.items(), key=lambda kv: len(kv[0]), reverse=True):
        if key in folded:
            slots.place_name = label
            if slots.location is None:
                slots.location = label
            break
    if _WEEK.search(raw):
        slots.duration_days = 7
    else:
        match = _DURATION.search(raw)
        if match:
            n = match.group("n") or match.group("n2") or match.group("n3")
            if n:
                days = int(n)
                if 1 <= days <= 60:
                    slots.duration_days = days

    for match in _BUDGET.finditer(raw):
        amount = _parse_int_amount(match.group("amount") or match.group("amount2") or "")
        if amount is not None:
            slots.budget_xaf = amount
            break

    people_match = _PEOPLE.search(raw)
    if people_match:
        n = people_match.group("n") or people_match.group("n2") or people_match.group("n3")
        if n:
            count = int(n)
            if 1 <= count <= 50:
                slots.people = count

    children_match = _CHILDREN.search(raw)
    if children_match:
        count = int(children_match.group("n"))
        if 0 <= count <= 20:
            slots.children = count

    interests: list[str] = []
    if re.search(r"\b(nature|ecotourisme|eco-?tourisme|parc|parcs)\b", folded):
        interests.append("nature")
    if re.search(r"\b(culture|culturel|patrimoine|sawa|bamil[eé]k[eé]|fang)\b", folded):
        interests.append("culture")
    if re.search(r"\b(plage|plages|mer|ocean|océan)\b", folded):
        interests.append("beach")
    if re.search(r"\b(gastronomie|cuisine|plat|plats|ndol[eé]|manger|food)\b", folded):
        interests.append("food")
    if re.search(r"\b(hotel|hôtel|hebergement|hébergement)\b", folded):
        interests.append("hotel")
    if re.search(
        r"\b(autour|alentours|environs|proche|nearby|around|proximit[eé])\b",
        folded,
    ):
        interests.append("nearby")
    slots.interests = interests
    slots.interests = interests

    if re.search(r"\b(luxe|premium|haut\s+de\s+gamme)\b", folded):
        slots.travel_style = "luxury"
    elif re.search(r"\b(backpack|budget|pas\s+cher|economique|économique)\b", folded):
        slots.travel_style = "budget"
    elif re.search(r"\b(famille|family)\b", folded):
        slots.travel_style = "family"

    slots.origin, slots.destination = _extract_route(folded)
    if slots.destination:
        # The destination is the tourism context; the origin only matters for the route.
        slots.city = slots.destination
        slots.location = slots.destination
    slots.dish = _extract_dish(folded)
    slots.wants_activities = bool(_ACTIVITIES.search(folded))
    slots.wants_images = bool(_IMAGE_REQUEST.search(folded)) or bool(
        slots.dish and _SEE_WORD.search(folded)
    )
    if not slots.dish and not slots.destination and not slots.wants_activities:
        slots.image_subject = _extract_image_subject(raw)
        if slots.image_subject:
            slots.wants_images = True
    slots.on_site = bool(_ON_SITE.search(folded))
    slots.return_trip = bool(_RETURN_CUE.search(folded))

    return slots
