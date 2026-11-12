"""Text rules shared by the library and the generator. js/text.js mirrors this file."""
from __future__ import annotations

import re
import unicodedata

# Articles that the INE writes after a comma («Coruña, A», «Orxa, l'», «Bòrdes, Es») or, in the street
# register, in brackets and in capitals («DEVESA (A)», «ESTEPAR (L')»). Per language, so that other
# countries can add theirs.
ARTICLES = {
    "es": ("El", "La", "Los", "Las"),
    "gl": ("O", "A", "Os", "As"),
    "ca": ("El", "La", "Els", "Les", "L'", "Es", "Sa", "Ses"),
    "oc": ("Eth", "Era", "Es", "Eras"),
}
_ARTICLES = {a.lower() for group in ARTICLES.values() for a in group}
_BY_LENGTH = sorted(_ARTICLES, key=lambda a: (-len(a), a))
_TRAILING_ARTICLES = (re.compile(r"^(?P<name>.+), (?P<article>[^,/]+)$"),
                      re.compile(r"^(?P<name>.+) \((?P<article>[^()/]+)\)$"))
_APOSTROPHES = re.compile("[’‘´`]")


def flip_article(name: str) -> str:
    """«Coruña, A» -> «A Coruña»; «Orxa, l'» -> «l'Orxa»; «DEVESA (A)» -> «A DEVESA». Other commas
    and brackets stay as they are («BURRES (SAN VICENTE)»)."""
    name = name.strip()
    for pattern in _TRAILING_ARTICLES:
        match = pattern.match(name)
        if match:
            article = _APOSTROPHES.sub("'", match["article"])
            if article.lower() in _ARTICLES:
                joiner = "" if article.endswith("'") else " "
                return f"{article}{joiner}{match['name']}"
    return name


def display_name(official: str) -> str:
    """Official INE name with each article in front: «Vila Joiosa, la/Villajoyosa» ->
    «la Vila Joiosa/Villajoyosa»."""
    return "/".join(flip_article(part) for part in official.split("/"))


def drop_article(name: str) -> str | None:
    """«A Coruña» -> «Coruña», «LA PULGOSA» -> «PULGOSA»; None if the name does not start with an
    article."""
    lower = name.lower()
    for article in _BY_LENGTH:
        if article.endswith("'") and lower.startswith(article) and len(name) > len(article):
            return name[len(article):]
        if lower.startswith(article + " ") and len(name) > len(article) + 1:
            return name[len(article) + 1:]
    return None


def normalize(text: str) -> str:
    """Comparison key: article in front, no accents or capitals, «l·l» as «ll», dashes and
    punctuation as spaces. Apostrophes are kept («l'hospitalet»)."""
    if not isinstance(text, str):
        return ""
    plain = unicodedata.normalize("NFKD", flip_article(_APOSTROPHES.sub("'", text)))
    plain = "".join(c for c in plain if not unicodedata.combining(c)).lower()
    plain = plain.replace("l·l", "ll").replace("l.l", "ll")
    plain = re.sub(r"[^a-z0-9']+", " ", plain)
    plain = re.sub(r"\s*'\s*", "'", plain)
    return re.sub(r"\s+", " ", plain).strip(" '")


def slugify(text: str) -> str:
    """«A Coruña» -> «a-coruna»; «Alicante/Alacant» -> «alicante-alacant»."""
    return re.sub(r"[^a-z0-9]+", "-", normalize(text)).strip("-")
