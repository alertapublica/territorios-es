"""Shared cases (casos.json), run against the fixture data. js/*.test.mjs runs the same cases."""
import json
import unittest
from pathlib import Path

from pruebas import ROOT
from territorios_es import Catalog, combine, load_entities, load_limits, locate, relation
from territorios_es.postal import PostalCodes, load_postal_codes
from territorios_es.catastro import check_letters, parse_cadastral_reference, relate_cadastral_reference
from territorios_es.relation import relate_name, to_municipality
from territorios_es.text import display_name, normalize

CASES = json.loads((ROOT / "pruebas" / "casos.json").read_text(encoding="utf-8"))
CATALOG = Catalog(json.loads((ROOT / "pruebas" / "datos" / "territorios.json").read_text(encoding="utf-8")))
ENTITIES = load_entities(ROOT / "pruebas" / "datos" / "entidades.csv", ROOT / "pruebas" / "datos" / "territorios.json")


class SharedCases(unittest.TestCase):
    def test_normalize(self):
        for text, expected in CASES["normalize"]:
            self.assertEqual(normalize(text), expected, text)

    def test_display_name(self):
        for official, expected in CASES["display_name"]:
            self.assertEqual(display_name(official), expected, official)

    def test_resolve(self):
        for system, code, expected, ancestors in CASES["resolve"]:
            found = CATALOG.resolve(system, code)
            self.assertEqual((found["id"], found["ancestors"]) if found else (None, None),
                             (expected, ancestors), (system, code))

    def test_children(self):
        for identity, expected in CASES["children"]:
            self.assertEqual(CATALOG.children(identity), expected, identity)

    def test_name(self):
        for identity, lang, short, expected in CASES["name"]:
            self.assertEqual(CATALOG.name(identity, lang, short), expected, (identity, lang, short))

    def test_search(self):
        for catalog in (CATALOG, ENTITIES):  # the same unless the entities are asked for
            for text, within, levels, expected in CASES["search"]:
                found = [[c["id"], c["reason"]] for c in catalog.search(text, within=within, levels=levels)]
                self.assertEqual(found, expected, text)

    def test_mentions(self):
        for catalog in (CATALOG, ENTITIES):
            for text, levels, expected in CASES["mentions"]:
                options = {"levels": levels} if levels else {}
                found = [[m["text"], [c["id"] for c in m["candidates"]]] for m in catalog.mentions(text, **options)]
                self.assertEqual(found, expected, text)

    def test_relate_name(self):
        for text, within, levels, status, territory, candidates, reason in CASES["relate_name"]:
            found = relate_name(CATALOG, text, within=within, levels=levels)
            self.assertEqual((found["status"], found["territory"], found["candidates"], found["reason"]),
                             (status, territory, candidates, reason), text)

    def test_cadastral_reference(self):
        for text, expected in CASES["cadastral_reference"]:
            self.assertEqual(parse_cadastral_reference(text), expected, text)
        self.assertIsNone(parse_cadastral_reference(None))
        self.assertRaises(ValueError, check_letters, "13096A00100192")

    def test_relate_cadastral_reference(self):
        for text, status, territory, reason in CASES["relate_cadastral_reference"]:
            found = relate_cadastral_reference(CATALOG, text)
            self.assertEqual((found["status"], found["territory"], found["reason"]), (status, territory, reason), text)


class EntityCases(unittest.TestCase):
    CASES = CASES["entities"]

    def test_resolve(self):
        for system, code, expected, ancestors in self.CASES["resolve"]:
            found = ENTITIES.resolve(system, code)
            self.assertEqual((found["id"], found["ancestors"]) if found else (None, None),
                             (expected, ancestors), (system, code))

    def test_children(self):
        for identity, expected in self.CASES["children"]:
            self.assertEqual(ENTITIES.children(identity), expected, identity)

    def test_search(self):
        for text, within, levels, expected in self.CASES["search"]:
            found = [[c["id"], c["reason"]] for c in ENTITIES.search(text, within=within, levels=levels)]
            self.assertEqual(found, expected, text)

    def test_to_municipality(self):
        for text, within, levels, status, territory, candidates, reason in self.CASES["to_municipality"]:
            found = to_municipality(ENTITIES, relate_name(ENTITIES, text, within=within, levels=levels))
            self.assertEqual((found["status"], found["territory"], found["candidates"], found["reason"]),
                             (status, territory, candidates, reason), text)

    def test_records_and_links(self):
        record = ENTITIES.territory("es:entidad:36038010101")
        self.assertEqual(record["codes"], {"ine:entidad": "36038010101", "ine:entidad:dc": "360380101601"})
        # The IGN núcleo with this code is called otherwise («A Devesa de Alba»): the rule, not reviewed.
        self.assertEqual(record["names"], {"official": "DEVESA (A)", "display": "A Devesa", "reviewed": False,
                                           "source": "regla"})
        self.assertEqual(ENTITIES.territory("es:entidad:36038010100")["names"],
                         {"official": "DEVESA (A)", "display": "A Devesa", "reviewed": False, "source": "ign_lugar",
                          "ref": "ign:opob/10"})
        self.assertEqual(ENTITIES.name("es:entidad:33031030299"), "Diseminado de La Talaya")
        self.assertEqual(ENTITIES.territory("es:entidad:08101000101")["names"]["display"], "L'Hospitalet de Llobregat")
        self.assertEqual((record["municipality"], record["collective_entity"]),
                         ("es:municipio:36038", "es:entidad:36038010000"))
        self.assertNotIn("collective_entity", ENTITIES.territory("es:entidad:36038000101"))
        first = ENTITIES.search("A Devesa", levels=["singular_entity"])[0]
        self.assertEqual((first["municipality"], first["collective_entity"]), ("es:municipio:36008", "es:entidad:36008030000"))
        self.assertNotIn("municipality", ENTITIES.search("Pontevedra")[0])
        self.assertEqual(ENTITIES.ids("collective_entity"),
                         ["es:entidad:33031030000", "es:entidad:36008030000", "es:entidad:36038010000"])
        self.assertEqual(CATALOG.ids("nucleus"), [])
        self.assertIsNone(CATALOG.resolve("ine:entidad", "36038010101"))
        # Linked: an entity and the municipality that holds it are not a contradiction once projected.
        entity, town = relate_name(ENTITIES, "Talaya", levels=["singular_entity"]), relate_name(ENTITIES, "Langreo")
        self.assertEqual(combine(entity, town)["status"], "conflict")
        self.assertEqual(combine(to_municipality(ENTITIES, entity), town)["territory"], "es:municipio:33031")
        self.assertEqual(to_municipality(ENTITIES, entity)["evidence"][-1],
                         {"source": "municipality", "datum": "es:entidad:33031030200", "territory": "es:municipio:33031"})

    def test_rejects_bad_tables(self):
        data = json.loads((ROOT / "pruebas" / "datos" / "territorios.json").read_text(encoding="utf-8"))
        good = (ROOT / "pruebas" / "datos" / "entidades.csv").read_text(encoding="utf-8")
        Catalog(data, good)
        reviewed = Catalog(data, good.replace("ALBA,Alba,regla,", "ALBA,Santa María de Alba,manual,rag"))
        self.assertEqual(reviewed.territory("es:entidad:36038010000")["names"],
                         {"official": "ALBA", "display": "Santa María de Alba", "reviewed": True, "source": "manual", "ref": "rag"})
        for bad in ("id,ine,official\n",
                    good + "es:entidad:36017151100,360171511700,DEVESA (A),A Devesa,regla,\n",  # unknown municipality
                    good + "es:entidad:36038020100,360380201600,SIN PARROQUIA,Sin Parroquia,regla,\n",  # missing collective
                    good + "es:entidad:x,360380101601,DEVESA (A),A Devesa,regla,\n",  # repeated code
                    good + "es:entidad:36038000000,360380000000,MUNICIPIO,Municipio,regla,\n",  # not an entity
                    good + "es:entidad:36038010102,3603801016,CORTO,Corto,regla,\n",
                    good + "es:entidad:36038010102,360380101602,,X,regla,\n",
                    good + "es:entidad:36038010102,360380101602,X,,regla,\n",  # no name to show
                    good + "es:entidad:36038010102,360380101602,X,X,otra,\n",  # unknown source
                    good + "es:entidad:36038010102,360380101602,X\n"):
            self.assertRaises(ValueError, Catalog, data, bad)


class PostalCodeCases(unittest.TestCase):
    TABLE = load_postal_codes(ROOT / "pruebas" / "datos" / "codigos-postales.csv")

    def test_postal_codes(self):
        for identity, expected in CASES["postal_codes"]:
            self.assertEqual([i["postal_code"] for i in self.TABLE.postal_codes(identity)], expected, identity)

    def test_municipalities(self):
        for code, expected in CASES["municipalities"]:
            self.assertEqual([[i["id"], i["count"], i["unit"]] for i in self.TABLE.municipalities(code)], expected, code)

    def test_relate_postal_code(self):
        for code, status, territory, candidates, reason in CASES["relate_postal_code"]:
            found = self.TABLE.relate(code)
            self.assertEqual((found["status"], found["territory"], found["candidates"], found["reason"]),
                             (status, territory, candidates, reason), code)

    def test_evidence_and_combine(self):
        found = self.TABLE.relate("15001")
        self.assertEqual([(e["territory"], e["origin"], e["count"], e["unit"], e["also"]) for e in found["evidence"]],
                         [("es:municipio:15030", "ine", 30, "street_sections", ["catastro"]),
                          ("es:municipio:36038", "catastro", 40, "addresses", [])])
        self.assertEqual(combine(found, relate_name(CATALOG, "A Coruña", levels=["municipality"]))["territory"],
                         "es:municipio:15030")
        first = self.TABLE.municipalities("15001")[0]
        self.assertEqual((first["source"], first["also"]), ("ine", ["catastro"]))
        first["count"], first["also"][0] = 0, "x"  # a copy: the table does not change
        self.assertEqual(self.TABLE.municipalities("15001")[0], {
            "postal_code": "15001", "id": "es:municipio:15030", "source": "ine", "count": 30,
            "unit": "street_sections", "also": ["catastro"]})
        self.assertEqual(len(self.TABLE), 23)
        self.assertRaises(ValueError, PostalCodes, "codigo,municipio\n")


class Locate(unittest.TestCase):
    LIMITS = load_limits(ROOT / "pruebas" / "limites.json")

    def test_locate(self):
        for lon, lat, status, territory, candidates, reason in CASES["locate"]:
            found = locate(lon, lat, self.LIMITS)
            self.assertEqual((found["status"], found["territory"], found["candidates"], found["reason"]),
                             (status, territory, candidates, reason), (lon, lat))

    def test_evidence_and_files(self):
        import gzip
        import tempfile
        found = locate(0.9999, 0.5, self.LIMITS)
        self.assertEqual([(e["territory"], e["inside"], e["distance_m"]) for e in found["evidence"]],
                         [("es:municipio:15030", True, 11.1), ("es:municipio:32054", False, 11.1)])
        self.assertEqual(self.LIMITS.attribution, "Obra derivada de BDLJE Continua CC-BY 4.0 ign.es")
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "limites-municipios.geojson.gz"
            path.write_bytes(gzip.compress((ROOT / "pruebas" / "limites.json").read_bytes()))
            self.assertEqual(locate(0.5, 0.5, path)["territory"], "es:municipio:15030")
        for bad in ((float("nan"), 0), (200, 0), ("1", 0)):
            self.assertRaises(ValueError, locate, *bad, self.LIMITS)
        self.assertEqual(locate(0.9999, 0.5, self.LIMITS, margin=5)["status"], "resolved")


class Relations(unittest.TestCase):
    def test_combine(self):
        a = relation("resolved", "es:municipio:32054", ["es:municipio:32054"])
        b = relation("pending", None, ["es:municipio:32054", "es:provincia:32"])
        c = relation("resolved", "es:provincia:32", ["es:provincia:32"])
        nothing = relation("pending", None, [], "not_found")
        self.assertEqual(combine(a, b)["status"], "resolved")
        self.assertEqual(combine(a, nothing)["territory"], "es:municipio:32054")
        self.assertEqual(combine(a, c)["status"], "conflict")
        self.assertEqual(combine(b, b)["status"], "pending")
        self.assertEqual(combine(nothing)["status"], "pending")
        self.assertEqual(combine(a, relation("conflict", None, ["x"]))["status"], "conflict")
        with self.assertRaises(ValueError):
            relation("resolved")


class CatalogValidation(unittest.TestCase):
    def test_rejects_repeated_codes_and_unknown_parents(self):
        base = {"schema": 1, "territories": [
            {"id": "a", "level": "country", "parent": None, "codes": {"x": "1"}, "names": {"official": "A", "display": "A"}}]}
        Catalog(base)
        twice = {**base, "territories": base["territories"] * 2}
        self.assertRaises(ValueError, Catalog, twice)
        orphan = {**base, "territories": [{**base["territories"][0], "parent": "z"}]}
        self.assertRaises(ValueError, Catalog, orphan)
        loop = {**base, "territories": [{**base["territories"][0], "parent": "b"},
                                        {**base["territories"][0], "id": "b", "parent": "a", "codes": {}}]}
        self.assertRaises(ValueError, Catalog, loop)
        self.assertRaises(ValueError, Catalog, {"schema": 2, "territories": []})

    def test_within_must_exist(self):
        self.assertRaises(ValueError, CATALOG.search, "Ourense", within="es:provincia:99")


if __name__ == "__main__":
    unittest.main()
