"""Spanish territories and countries: codes, names in every official language, search.

    import territorios_es as te
    te.resolve("ine:municipio", "36038")["id"]   # 'es:municipio:36038'
    te.name("es:provincia:03", "ca")             # 'Alacant'
"""
from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

from .catalog import LEVELS, REASONS, Catalog
from .catastro import check_letters, parse_cadastral_reference
from .catastro import relate_cadastral_reference as _relate_cadastral_reference
from .limits import Limits, load_limits, locate
from .relation import STATUSES, combine, relation
from .relation import relate_name as _relate_name
from .text import display_name, normalize, slugify

__all__ = ["Catalog", "LEVELS", "REASONS", "STATUSES", "load", "resolve", "territory", "search",
           "mentions", "name", "children", "normalize", "display_name", "slugify", "relation",
           "relate_name", "combine", "data_dir", "parse_cadastral_reference", "check_letters",
           "relate_cadastral_reference", "Limits", "load_limits", "locate"]


def data_dir() -> Path:
    """Folder with the generated data: $TERRITORIOS_ES_DATOS, the copy inside the installed
    package, or datos/ in a checkout of the repository."""
    if os.environ.get("TERRITORIOS_ES_DATOS"):
        return Path(os.environ["TERRITORIOS_ES_DATOS"])
    here = Path(__file__).resolve().parent
    for folder in (here / "datos", here.parents[1] / "datos"):
        if (folder / "territorios.json").exists():
            return folder
    raise FileNotFoundError("territorios.json not found; set TERRITORIOS_ES_DATOS")


@lru_cache(maxsize=4)
def load(path: str | os.PathLike | None = None) -> Catalog:
    """Catalogue from a territorios.json file (by default, the bundled one)."""
    file = Path(path) if path else data_dir() / "territorios.json"
    return Catalog(json.loads(file.read_text(encoding="utf-8")))


def resolve(system, code):
    return load().resolve(system, code)


def territory(identity):
    return load().territory(identity)


def search(text, within=None, levels=None):
    return load().search(text, within=within, levels=levels)


def mentions(text, levels=("autonomous_community", "province"), within=None):
    return load().mentions(text, levels=levels, within=within)


def name(identity, lang="es", short=False):
    return load().name(identity, lang=lang, short=short)


def children(identity):
    return load().children(identity)


def relate_name(text, within=None, levels=None, catalog=None):
    return _relate_name(catalog or load(), text, within=within, levels=levels)


def relate_cadastral_reference(text, catalog=None):
    return _relate_cadastral_reference(catalog or load(), text)
