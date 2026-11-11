"""Catalogue of territories built from datos/territorios.json. js/catalog.js mirrors this file."""
from __future__ import annotations

import re
from copy import deepcopy

from .text import drop_article, normalize

LEVELS = ("country", "autonomous_community", "province", "island", "municipality", "judicial_district",
          "warning_zone", "comarca")
# Groups of municipalities that do not change their parent: the field of the municipality that names
# its group is the level of the group.
GROUPS = ("island", "judicial_district", "warning_zone", "comarca")
# Levels that search() leaves out unless asked for: a judicial district has the name of its seat, a
# warning zone of AEMET is not an administration and a comarca exists only in some communities (and
# some share their name with a municipality).
UNSEARCHED_LEVELS = ("judicial_district", "warning_zone", "comarca")
# Order of the reasons why a text matches a territory, best first.
REASONS = ("official", "part", "lang", "alias", "variant")
DEFAULT_MENTION_LEVELS = ("autonomous_community", "province")
# Levels whose name is translated in each language (§4.4 of the design); the others show the
# official name, or the part of a bilingual official name in the page language.
TRANSLATED_LEVELS = ("country", "autonomous_community")


class Catalog:
    def __init__(self, data: dict):
        if data.get("schema") != 1:
            raise ValueError("Unsupported data schema")
        self.reference_date = data.get("reference_date")
        self._by_id: dict[str, dict] = {}
        self._codes: dict[tuple[str, str], str] = {}
        self._children: dict[str, list[str]] = {}
        for record in data["territories"]:
            identity = record.get("id")
            if not isinstance(identity, str) or identity in self._by_id:
                raise ValueError(f"Missing or repeated id: {identity!r}")
            if record.get("level") not in LEVELS:
                raise ValueError(f"Unknown level in {identity}")
            names = record.get("names") or {}
            if not names.get("official") or not names.get("display"):
                raise ValueError(f"Missing official or display name in {identity}")
            for system, code in (record.get("codes") or {}).items():
                if not isinstance(code, str) or not code or (system, code) in self._codes:
                    raise ValueError(f"Invalid or repeated code {system}={code!r} in {identity}")
                self._codes[system, code] = identity
            self._by_id[identity] = record
        for identity, record in self._by_id.items():
            parent = record.get("parent")
            if parent is not None:
                if parent not in self._by_id:
                    raise ValueError(f"Unknown parent {parent} of {identity}")
                self._children.setdefault(parent, []).append(identity)
            # An island, a judicial district, a warning zone or a comarca groups municipalities, whose
            # parent stays the province.
            for group in GROUPS:
                member_of = record.get(group)
                if member_of is not None:
                    if self._by_id.get(member_of, {}).get("level") != group:
                        raise ValueError(f"Unknown {group} {member_of} of {identity}")
                    self._children.setdefault(member_of, []).append(identity)
        self._index = self._build_index()
        self._mention_patterns: dict[tuple[str, ...], tuple[re.Pattern | None, dict]] = {}

    # Codes and records -------------------------------------------------------------------------

    def ancestors(self, identity: str) -> list[str]:
        result, parent = [], self._by_id[identity].get("parent")
        while parent:
            result.append(parent)
            parent = self._by_id[parent].get("parent")
        return result

    def territory(self, identity: str) -> dict | None:
        """Full record with its ancestors, or None."""
        record = self._by_id.get(identity) if isinstance(identity, str) else None
        if record is None:
            return None
        return {**deepcopy(record), "ancestors": self.ancestors(identity)}

    def resolve(self, system: str, code: str) -> dict | None:
        """Territory for a code of a given system. Codes are strings: no zero padding, no
        guessing the system."""
        if not isinstance(code, str):
            return None
        identity = self._codes.get((system, code))
        return self.territory(identity) if identity else None

    def children(self, identity: str) -> list[str]:
        """Territories whose parent is this one; for an island, a judicial district, a warning zone or
        a comarca, its municipalities."""
        return sorted(self._children.get(identity, []))

    def ids(self, level: str | None = None) -> list[str]:
        return sorted(i for i, r in self._by_id.items() if level is None or r["level"] == level)

    # Names ---------------------------------------------------------------------------------------

    def name(self, identity: str, lang: str = "es", short: bool = False) -> str | None:
        """Display name in a language (design §4.4)."""
        record = self._by_id.get(identity) if isinstance(identity, str) else None
        if record is None:
            return None
        names = record["names"]
        if record["level"] in TRANSLATED_LEVELS:
            if short and lang in names.get("short", {}):
                return names["short"][lang]
            if lang in names.get("lang", {}):
                return names["lang"][lang]
            return names["display"]
        return names.get("parts", {}).get(lang, names["display"])

    def _forms(self, record: dict):
        """(text, reason, lang) for every name a territory can be searched by."""
        names = record["names"]
        yield names["official"], "official", None
        yield names["display"], "official", None
        for lang, part in names.get("parts", {}).items():
            yield part, "part", lang
        for group in ("lang", "short"):
            for lang, value in names.get(group, {}).items():
                yield value, "lang", lang
        for alias in names.get("aliases", []):
            yield alias["name"], "alias", alias.get("lang")
        variants = [names["display"], *names.get("parts", {}).values(), *names.get("lang", {}).values()]
        for value in variants:
            shorter = drop_article(value)
            if shorter:
                yield shorter, "variant", None

    def _build_index(self) -> dict[str, list[tuple[int, int, str, str, str | None]]]:
        best: dict[tuple[str, str], tuple[int, str, str | None]] = {}
        for identity, record in self._by_id.items():
            for text, reason, lang in self._forms(record):
                key = normalize(text)
                if not key:
                    continue
                rank = REASONS.index(reason)
                current = best.get((key, identity))
                if current is None or (rank, lang or "") < (current[0], current[2] or ""):
                    best[key, identity] = (rank, reason, lang)
        index: dict[str, list] = {}
        for (key, identity), (rank, reason, lang) in best.items():
            level = LEVELS.index(self._by_id[identity]["level"])
            index.setdefault(key, []).append((rank, level, identity, reason, lang))
        for entries in index.values():
            entries.sort(key=lambda e: (e[0], e[1], e[2]))
        return index

    def _candidate(self, entry) -> dict:
        _, _, identity, reason, lang = entry
        record = self._by_id[identity]
        return {"id": identity, "level": record["level"], "name": record["names"]["display"],
                "reason": reason, "lang": lang}

    def _accept(self, identity: str, within: str | None, levels) -> bool:
        level = self._by_id[identity]["level"]
        if level not in (levels if levels is not None else set(LEVELS) - set(UNSEARCHED_LEVELS)):
            return False
        if within is None or within in self.ancestors(identity):
            return True
        return any(self._by_id[identity].get(group) == within for group in GROUPS)

    # Search ----------------------------------------------------------------------------------------

    def search(self, text: str, within: str | None = None, levels=None) -> list[dict]:
        """Candidates whose name is the whole text, best first. Never picks one for you."""
        if within is not None and within not in self._by_id:
            raise ValueError(f"Unknown territory {within}")
        entries = self._index.get(normalize(text), [])
        return [self._candidate(e) for e in entries if self._accept(e[2], within, levels)]

    def mentions(self, text: str, levels=DEFAULT_MENTION_LEVELS, within: str | None = None) -> list[dict]:
        """Names found inside a longer text, left to right; at each position the longest name
        wins and matches do not overlap. Each mention keeps all its candidates."""
        levels = tuple(levels)
        if levels not in self._mention_patterns:
            forms = {key: [e for e in entries if self._by_id[e[2]]["level"] in levels]
                     for key, entries in self._index.items()}
            forms = {key: entries for key, entries in forms.items() if entries}
            ordered = sorted(forms, key=lambda key: (-len(key), key))
            pattern = re.compile(r"(?<![a-z0-9])(?:" + "|".join(map(re.escape, ordered)) + r")(?![a-z0-9])") \
                if ordered else None
            self._mention_patterns[levels] = (pattern, forms)
        pattern, forms = self._mention_patterns[levels]
        if pattern is None:
            return []
        found = []
        for match in pattern.finditer(normalize(text)):
            candidates = [self._candidate(e) for e in forms[match.group()] if self._accept(e[2], within, levels)]
            if candidates:
                found.append({"text": match.group(), "candidates": candidates})
        return found
