"""Text rules shared by the library and the generator. js/text.js mirrors this file."""
from __future__ import annotations

import re
import unicodedata

# Articles that the INE writes after a comma: «Coruña, A», «Orxa, l'», «Bòrdes, Es».
# Per language, so that other countries can add theirs.
ARTICLES = {
    "es": ("El", "La", "Los", "Las"),
    "gl": ("O", "A", "Os", "As"),
    "ca": ("El", "La", "Els", "Les", "L'", "Es", "Sa", "Ses"),
    "oc": ("Eth", "Era", "Es", "Eras"),
}
_ARTICLES = {a for group in ARTICLES.values() for a in group}
_ARTICLES |= {a.lower() for a in _ARTICLES}
_BY_LENGTH = sorted(_ARTICLES, key=lambda a: (-len(a), a))
_TRAILING_ARTICLE = re.compile(r"^(?P<name>.+), (?P<article>[^,/]+)$")
_APOSTROPHES = re.compile("[’‘´`]")


def flip_article(name: str) -> str:
    """«Coruña, A» -> «A Coruña»; «Orxa, l'» -> «l'Orxa». Other commas stay as they are."""
    match = _TRAILING_ARTICLE.match(name.strip())
    if not match:
        return name.strip()
    article = _APOSTROPHES.sub("'", match["article"])
    if article not in _ARTICLES:
        return name.strip()
    joiner = "" if article.endswith("'") else " "
    return f"{article}{joiner}{match['name']}"


def display_name(official: str) -> str:
    """Official INE name with each article in front: «Vila Joiosa, la/Villajoyosa» ->
    «la Vila Joiosa/Villajoyosa»."""
    return "/".join(flip_article(part) for part in official.split("/"))


def drop_article(name: str) -> str | None:
    """«A Coruña» -> «Coruña»; None if the name does not start with an article."""
    for article in _BY_LENGTH:
        if article.endswith("'") and name.startswith(article) and len(name) > len(article):
            return name[len(article):]
        if name.startswith(article + " ") and len(name) > len(article) + 1:
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
