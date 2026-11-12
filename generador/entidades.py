"""Population entities (entidades de población) of the INE street register: writes datos/entidades.csv
from the population units file (UP…) of the same ZIP that codigos_postales reads its street sections
from (design §4.1). One row per entity: identifier, 12-digit code, the name as the INE writes it
and the name to show, with where it comes from (design §4.3); the library takes the level and the
parent from the code (python/territorios_es/entities.py).

The name to show, in this order: a hand correction in fuentes/nombres-entidades.csv, if the INE
still writes the name it expects (`manual`); the spelling of the IGN núcleo with the same code
(`ign`) or of a population place of the IGN inside that entity (`ign_lugar`), if only capitals and
accents change; and if there is none, a rule of capitals and articles for the INE names, by
language (`regla`). A scattered part shows the name of its singular entity (`derivado`). What the
IGN calls otherwise, accents it would add and places of the municipality with the same name go to
the report, never to the name.
"""
from __future__ import annotations

import csv
import io
import re
import unicodedata
from collections import Counter, defaultdict

from territorios_es.entities import ENTITY_HEADER, ENTITY_LEVELS, entity_code, entity_level
from territorios_es.text import flip_article

from .codigos_postales import ine_register_file

FILE = "entidades.csv"
CORRECTIONS = "nombres-entidades.csv"  # in fuentes/
# Fixed width (cp1252): code at 0–12; names of the collective entity, the singular entity and the
# nucleus (or «*DISEMINADO*») at these positions.
NAMES = {"collective_entity": (169, 239), "singular_entity": (314, 384), "nucleus": (459, 529),
         "scattered": (459, 529)}
LEVEL_NAMES = {"collective_entity": "colectivas", "singular_entity": "singulares", "nucleus": "núcleos",
               "scattered": "diseminados"}
SECTION = "Entidades de población que no se publican"
NAME_SECTIONS = {"other": "Entidades de población: otro nombre en el IGN",
                 "spellings": "Entidades de población: varias grafías en el IGN",
                 "proposals": "Entidades de población: nombre que propone un lugar del municipio",
                 "accents": "Entidades de población: tildes que propone el IGN",
                 "review": "Entidades de población: correcciones a mano que hay que revisar",
                 "capitals": "IGN: capital sin entidad del INE"}
CORRECTION_HEADER = ["id", "official", "display", "source", "date"]
POPULATIONS = {"NUC", "OPOB", "NUCL", "BARR", "URBA"}  # kinds of IGN places; the rest are facilities
SCATTERED_LABEL = "Diseminado de {}"
# Language of the rule by province; words written in lower case inside a name, besides the Spanish ones.
LANGUAGES = {**dict.fromkeys(("15", "27", "32", "36"), "gl"),
             **dict.fromkeys(("03", "07", "08", "12", "17", "25", "43", "46"), "ca"),
             **dict.fromkeys(("01", "20", "31", "48"), "eu"), "33": "ast"}
LOWER = {"es": {"de", "del", "la", "las", "los", "el", "y", "e", "o", "u", "a", "al", "en", "con", "sobre", "entre"},
         "gl": {"da", "do", "das", "dos", "as", "os", "no", "na", "nos", "nas", "ao", "aos"},
         "ca": {"dels", "les", "els", "i", "na", "es", "sa", "ses", "des", "so", "per", "pel", "als"},
         "eu": {"eta"},
         "ast": {"les", "lu"}}
_ROMAN = re.compile(r"(?=[ivxlc]{2,}$)c{0,3}(xc|xl|l?x{0,3})(ix|iv|v?i{0,3})")
_NOT_ROMAN = {"vil", "mil", "lix", "dix", "cid", "civil"}
_TOKENS = re.compile(r"(\s+|-|/|\.(?!l)|\(|\))")
_ELIDED = re.compile(r"([dlsn]')(.+)")
_KEEP = {"\u0303", "\u0327"}  # the tilde of ñ and the cedilla of ç are letters, not accents
_CODE = re.compile(r"[0-9]{12}")


def parse_units(content: bytes) -> list[tuple[str, str]]:
    """[(12-digit code, official name)] of the entities in the population units file of the street
    register ZIP, read line by line. Municipality rows are left out."""
    archive, name = ine_register_file(content, "UP", "unidades poblacionales")
    units, lines, odd = [], 0, 0
    with archive.open(name) as stream:
        for raw in stream:
            lines += 1
            line = raw.decode("cp1252")
            code = line[0:12]
            if not _CODE.fullmatch(code):
                odd += 1
                continue
            level = entity_level(entity_code(code))
            if level is not None:
                start, end = NAMES[level]
                units.append((code, line[start:end].strip()))
    if not units or odd > lines * 0.01:
        raise ValueError(f"INE: {odd} de {lines} unidades poblacionales sin la forma esperada")
    return units


def same_name(name: str) -> str:
    """Comparison key for two spellings of one name: article in front, no capitals and no accents,
    but ñ and ç kept («PEÑA» is not «Pena») and «l·l» as «l.l», as the INE writes it."""
    name = flip_article(name.strip()).lower().replace("l·l", "l.l")
    name = "".join(c for c in unicodedata.normalize("NFD", name) if not unicodedata.combining(c) or c in _KEEP)
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", name))


def language(code: str) -> str:
    return LANGUAGES.get(code[:2], "es")


def recase(official: str, lang: str = "es") -> str:
    """Rule for the INE names, which are in capitals and without some accents: «DEVESA (A)» -> «A
    Devesa», «PONTE DA BARCA» -> «Ponte da Barca», «MAS D'EN GUAL» -> «Mas d'en Gual». Only for
    these names, not for other texts (streets, places, bodies)."""
    lower = LOWER["es"] | LOWER.get(lang, set())
    out = []
    for part in official.split("/"):
        words, first = [], True
        tokens = _TOKENS.split(flip_article(part).lower())
        last = max((i for i, token in enumerate(tokens) if token and not _TOKENS.fullmatch(token)), default=-1)
        for i, token in enumerate(tokens):
            if not token or _TOKENS.fullmatch(token):
                words.append(token)
                continue
            elided = _ELIDED.fullmatch(token)
            if elided:
                article, rest = elided[1].upper() if first else elided[1], elided[2]
                words.append(article + (rest if not first and rest in lower else rest[:1].upper() + rest[1:]))
            elif not first and token in lower and i != last:  # «MAS-TRADER I»: no particle at the end
                words.append(token)
            elif token == "i" and i == last:
                words.append("I")
            elif _ROMAN.fullmatch(token) and token not in _NOT_ROMAN:
                words.append(token.upper())
            else:
                words.append(token[:1].upper() + token[1:])
            first = False
        out.append("".join(words))
    return "/".join(out)


def _initial(name: str) -> str:
    return name[:1].upper() + name[1:]  # «les Cases Noves» -> «Les Cases Noves», as for municipalities


def read_corrections(text: str) -> dict[str, dict]:
    """Hand corrections by identifier, from fuentes/nombres-entidades.csv."""
    rows = list(csv.DictReader(io.StringIO(text)))
    if (rows and list(rows[0]) != CORRECTION_HEADER) or (not rows and text.split("\n")[0].split(",") != CORRECTION_HEADER):
        raise ValueError(f"nombres-entidades.csv: la cabecera debe ser {','.join(CORRECTION_HEADER)}")
    found = {}
    for row in rows:
        if not all(row[k] for k in CORRECTION_HEADER) or row["id"] in found or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", row["date"]):
            raise ValueError(f"nombres-entidades.csv: fila no válida o repetida {row}")
        found[row["id"]] = row
    return found


def _spelling(official: str, scope: list[list[str]]) -> tuple[str | None, str, list[str]]:
    """(IGN spelling, its reference, the spellings when they disagree) among the population places
    of `scope` with the same name. A núcleo of the IGN goes before the other places."""
    key = same_name(official)
    matches = sorted((kind != "NUC", ref, name) for _, name, ref, kind in scope
                     if kind in POPULATIONS and same_name(name) == key)
    for group in ([m for m in matches if not m[0]], matches):
        spellings = sorted({name for _, _, name in group})
        if len(spellings) == 1:
            return spellings[0], group[0][1], []
        if spellings:
            return None, "", spellings
    return None, "", []


def names(rows: list[list[str]], places: list[list[str]], corrections: dict[str, dict], report) -> dict[str, int]:
    """Adds display, display_source and display_ref to each row of the table (sorted parents first
    or not: the scattered parts are done last). Returns the count per source."""
    by_code, by_9, by_7, municipal = defaultdict(list), defaultdict(list), defaultdict(list), defaultdict(list)
    for place in places:
        code = place[0]
        by_code[code].append(place)
        if code[5:] == "000000":
            municipal[code[:5]].append(place)  # only the municipality: not «of that entity»
        else:
            by_9[code[:9]].append(place)
            by_7[code[:7]].append(place)
    accents = _accents(places)
    used = set()
    by_short = {entity_code(row[1]): row for row in rows}
    for short, row in sorted(by_short.items(), key=lambda item: entity_level(item[0]) == "scattered"):
        identity, official, level = row[0], row[2], entity_level(short)
        for _, name, ref, kind in by_code.get(short, ()):
            if kind == "NUC" and same_name(name) != same_name(official):
                report.add(NAME_SECTIONS["other"], f"{identity} «{official}»: «{name}» ({ref})")
        fix = corrections.get(identity)
        if fix:
            used.add(identity)
            if fix["official"] == official:
                row += [fix["display"], "manual", fix["source"]]
                continue
            report.add(NAME_SECTIONS["review"], f"{identity}: el INE escribe ahora «{official}», no «{fix['official']}»")
        if level == "scattered":
            parent = by_short.get(short[:9] + "00")
            row += [SCATTERED_LABEL.format(parent[3]), "derivado", parent[0]]
            continue
        scope = (by_code.get(short, []) if level == "nucleus"
                 else by_9[short[:9]] if level == "singular_entity" else by_7[short[:7]])
        spelling, ref, disagree = _spelling(official, scope)
        if spelling:
            row += [_initial(spelling), "ign" if ref.startswith("ign:nuc/") and level == "nucleus" else "ign_lugar", ref]
            continue
        if disagree:
            report.add(NAME_SECTIONS["spellings"], f"{identity} «{official}»: {', '.join('«' + s + '»' for s in disagree)}")
        display = recase(official, language(short))
        row += [display, "regla", ""]
        proposal, ref, _ = _spelling(official, municipal.get(short[:5], []))
        if proposal:
            report.add(NAME_SECTIONS["proposals"], f"{identity} «{display}»: «{_initial(proposal)}» ({ref})")
        accented = _accented(display, accents.get(short[:2], {}))
        if accented != display:
            report.add(NAME_SECTIONS["accents"], f"{identity} «{display}»: «{accented}»")
    for identity in sorted(set(corrections) - used):
        report.add(NAME_SECTIONS["review"], f"{identity}: no está en el callejero")
    return Counter(row[4] for row in rows)


def _plain(word: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", word) if not unicodedata.combining(c) or c in _KEEP)


def _accents(places: list[list[str]], minimum: int = 3) -> dict[str, dict[str, str]]:
    """By province, the words that the IGN always writes with the same accents, at least `minimum`
    times: a proposal for the names made by the rule, never applied."""
    seen = defaultdict(lambda: defaultdict(Counter))
    for code, name, _, kind in places:
        if kind in POPULATIONS:
            for word in re.findall(r"[^\W\d_]+", name.lower()):
                seen[code[:2]][unicodedata.normalize("NFC", _plain(word))][word] += 1
    return {province: {plain: form for plain, forms in words.items() if len(forms) == 1
                       for form, n in forms.items() if n >= minimum and form != plain}
            for province, words in seen.items()}


def _accented(display: str, words: dict[str, str]) -> str:
    def one(match):
        form = words.get(unicodedata.normalize("NFC", _plain(match[0].lower())))
        if form is None:
            return match[0]
        return form[:1].upper() + form[1:] if match[0][:1].isupper() else form
    return re.sub(r"[^\W\d_]+", one, display)


def rule_check(rows: list[list[str]]) -> str:
    """How well the rule writes the núcleos whose spelling comes from the IGN núcleo with the same
    code: exactly and without counting accents, overall and by language (summary of the report)."""
    tally = defaultdict(lambda: [0, 0, 0])
    for row in rows:
        if row[4] == "ign":
            short = entity_code(row[1])
            made = recase(row[2], language(short))
            for lang in ("total", language(short)):
                tally[lang][0] += 1
                tally[lang][1] += made == row[3]
                tally[lang][2] += _plain(made) == _plain(row[3])
    if not tally:
        return "sin núcleos del IGN para comparar"
    def pct(a, b):
        return f"{100 * a / b:.1f} %".replace(".", ",")
    n, exact, plain = tally.pop("total")
    by_lang = ", ".join(f"{lang} {pct(t[2], t[0])} de {t[0]}" for lang, t in sorted(tally.items()))
    return (f"{pct(exact, n)} exacta y {pct(plain, n)} sin contar tildes, frente a {n} núcleos del IGN "
            f"(con la inicial en mayúscula); sin tildes, por idioma: {by_lang}")


def link_capitals(data: dict, rows: list[list[str]], report):
    """The entity of the capital of each municipality (capital.entity), if the street register has
    its code; capital.ine and capital.ign stay as the IGN gives them."""
    ids = {entity_code(row[1]): row[0] for row in rows}
    for territory in data["territories"]:
        capital = territory.get("capital")
        if capital:
            capital.pop("entity", None)
            if capital["ine"] in ids:
                capital["entity"] = ids[capital["ine"]]
            else:
                report.add(NAME_SECTIONS["capitals"], f"{territory['id']}: «{capital['name']}» ({capital['ine']})")


def build(units: list[tuple[str, str]], data: dict) -> tuple[list[list[str]], list[str], dict[str, int]]:
    """(rows of entidades.csv sorted by code, without the names to show yet; what is left out and why;
    count per level). An entity is left out if its municipality is not in the catalogue, it has no
    name, its code is repeated or its parent entity is missing: the library would refuse the table."""
    municipalities = {t["codes"]["ine:municipio"] for t in data["territories"]
                      if t["level"] == "municipality" and "ine:municipio" in t.get("codes", {})}
    kept, left_out, seen = {}, [], set()
    for code, name in sorted(units):
        short = entity_code(code)
        if short in seen:
            left_out.append(f"{code}: código repetido")
            continue
        seen.add(short)
        if code[:5] not in municipalities:
            left_out.append(f"{code} {name}: el municipio {code[:5]} no está en el catálogo")
        elif not name:
            left_out.append(f"{code}: sin nombre")
        else:
            kept[short] = [f"es:entidad:{short}", code, name]
    # Parents before children: collective, singular, nucleus or scattered part.
    for short in sorted(kept, key=lambda c: ENTITY_LEVELS.index(entity_level(c))):
        level = entity_level(short)
        parent = (short[:7] + "0000" if level == "singular_entity" and short[5:7] != "00"
                  else short[:9] + "00" if level in ("nucleus", "scattered") else None)
        if parent is not None and parent not in kept:
            left_out.append(f"{kept[short][1]} {kept[short][2]}: falta su entidad {parent}")
            del kept[short]
    rows = [kept[short] for short in sorted(kept, key=lambda c: kept[c][1])]
    counts = Counter(entity_level(entity_code(row[1])) for row in rows)
    return rows, left_out, {level: counts[level] for level in ENTITY_LEVELS}


def table(rows: list[list[str]]) -> str:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(ENTITY_HEADER)
    writer.writerows(rows)
    return out.getvalue()


def summary(counts: dict[str, int]) -> str:
    return ", ".join(f"{n:,}".replace(",", ".") + f" {LEVEL_NAMES[level]}" for level, n in counts.items())
