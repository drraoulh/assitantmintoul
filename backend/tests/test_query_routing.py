from app.services.ai.routing import route_query


def test_simple_greetings_skip_kb():
    for text in ("Bonjour", "bonjour !", "Merci", "Hello", "Salut"):
        route = route_query(text)
        assert route.skip_kb is True
        assert route.skip_web is True
        assert route.kind == "simple"


def test_tourism_queries_need_grounding():
    for text in (
        "Que visiter à Yaoundé ?",
        "Prix d'entrée du monument de la réunification",
        "Plages à Kribi",
    ):
        route = route_query(text)
        assert route.skip_kb is False
        assert route.kind == "grounded"
