"""Generator: readers and the build on the fixture inputs (pruebas/fuentes/entrada.json)."""
import io
import json
import unittest
from zipfile import ZipFile

from pruebas import ROOT
from generador import eurostat, exportar, ine, wikidata
from generador.construir import build
from generador.xlsx import read_rows


def xlsx(sheets: dict[str, list[list[str]]]) -> bytes:
    """Tiny XLSX with inline strings, enough for the readers."""
    out = io.BytesIO()
    with ZipFile(out, "w") as book:
        entries = "".join(f'<sheet name="{n}" sheetId="{i}" r:id="rId{i}"/>' for i, n in enumerate(sheets, 1))
        book.writestr("xl/workbook.xml", '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                      'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                      f"<sheets>{entries}</sheets></workbook>")
        rels = "".join(f'<Relationship Id="rId{i}" Target="worksheets/sheet{i}.xml"/>' for i in range(1, len(sheets) + 1))
        book.writestr("xl/_rels/workbook.xml.rels",
                      f'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">{rels}</Relationships>')
        for i, rows in enumerate(sheets.values(), 1):
            xml = "".join(
                f'<row r="{r}">' + "".join(f'<c r="{chr(65 + c)}{r}" t="inlineStr"><is><t>{v}</t></is></c>'
                                          for c, v in enumerate(row) if v != "") + "</row>"
                for r, row in enumerate(rows, 1))
            book.writestr(f"xl/worksheets/sheet{i}.xml",
                          f'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>{xml}</sheetData></worksheet>')
    return out.getvalue()


class Readers(unittest.TestCase):
    def test_ine_dictionary(self):
        content = xlsx({"Hoja": [["Relación de municipios a 1 de enero de 2026"],
                                 ["CODAUTO", "CPRO", "CMUN", "DC", "NOMBRE"],
                                 ["12", "36", "038", "8", "Pontevedra"], ["12", "15", "030", "8", "Coruña, A"]]})
        self.assertEqual(ine.parse_municipalities(content, "1 de enero de 2026"),
                         [["15030", "8", "Coruña, A", "12"], ["36038", "8", "Pontevedra", "12"]])
        self.assertRaises(ValueError, ine.parse_municipalities, content, "1 de enero de 2027")

    def test_ine_provinces_html(self):
        page = ("<table><tr><th>CODAUTO</th><th>Comunidad</th><th>CPRO</th><th>Provincia</th></tr>"
                "<tr><td>12</td><td>Galicia</td><td>15</td><td>Coru&ntilde;a, A</td></tr></table>").encode()
        self.assertEqual(ine.parse_provinces(page), [["15", "12", "Coruña, A"]])

    def test_lau_sheet_and_codes(self):
        # Header as in EU-27-LAU-2024-NUTS-2024.xlsx (seen in Actions on 2026-11-09).
        header = ["NUTS3", "LAU CODE", "EU LAU CODE", "LAU NAME NATIONAL", "LAU NAME LATIN", "CHANGE", "POPULATION",
                  "TOTAL AREA (m2)", "DEGURBA", "COASTAL AREA", "CITY ID", "CITY NAME", "FUA ID", "FUA_NAME"]
        content = xlsx({"BE": [["x"]], "ES": [header, ["ES114", "36038", "ES_36038", "Pontevedra", "Pontevedra", "no",
                                                        "84000", "118000000", "2", "yes", "ES013C", "Pontevedra", "ES013L", "x"]]})
        rows, header = eurostat.parse_lau(content, "ES")
        self.assertEqual(rows["36038"]["nuts3"], "ES114")
        self.assertEqual({k: rows["36038"][k] for k in ("lau", "area", "degurba", "coastal", "city", "fua")},
                         {"lau": "36038", "area": "118000000", "degurba": "2", "coastal": "yes", "city": "ES013C",
                          "fua": "ES013L"})
        self.assertEqual(header[1], "LAU CODE")
        self.assertEqual(read_rows(content, "BE"), [["x"]])
        self.assertEqual([eurostat.ine_code(c) for c in ("36038", "ES36038", "ES_36038", "3603", "PT1601")],
                         ["36038", "36038", "36038", None, None])

    def test_find_link(self):
        page = b'<a href="/eurostat/documents/1/2/EU-27-LAU-2024-NUTS-2024.xlsx/abc?t=1">x</a>'
        self.assertEqual(eurostat.find_link(page, r"LAU-2024-NUTS-2024\.xlsx", "https://ec.europa.eu"),
                         "https://ec.europa.eu/eurostat/documents/1/2/EU-27-LAU-2024-NUTS-2024.xlsx/abc?t=1")

    def test_wikidata_parse(self):
        def results(rows):
            return json.dumps({"results": {"bindings": rows}}).encode()
        uri = {"value": "http://www.wikidata.org/entity/Q1"}
        raw = {"spain_codes": results([{"item": uri, "ine": {"value": "36038"}, "osm": {"value": "1"}},
                                       {"item": uri, "ine": {"value": "36038"}, "osm": {"value": "2"}}]),
               "spain_labels": results([{"item": uri, "label": {"value": "Pontevedra", "xml:lang": "gl"}}]),
               "spain_articles": results([{"item": uri, "article": {"value": "https://gl.wikipedia.org/wiki/Pontevedra_%C3%A1"}}])}
        items = wikidata.parse(raw, "spain")
        self.assertEqual(items["Q1"]["codes"]["osm"], {"1", "2"})
        self.assertEqual(items["Q1"]["labels"], {"gl": "Pontevedra"})
        self.assertEqual(items["Q1"]["articles"], {"gl": "Pontevedra á"})
        queries = wikidata.queries()
        self.assertEqual(len(queries), 2 * (1 + 2 * len(wikidata.LANGS)))
        self.assertIn('FILTER(LANG(?label) = "eu")', queries["spain_labels_eu"])
        self.assertIn("<https://gl.wikipedia.org/>", queries["country_articles_gl"])


class Build(unittest.TestCase):
    def setUp(self):
        inputs = json.loads((ROOT / "pruebas" / "fuentes" / "entrada.json").read_text(encoding="utf-8"))
        inputs["wikidata_spain"] = wikidata.from_jsonable(inputs["wikidata_spain"])
        inputs["wikidata_countries"] = wikidata.from_jsonable(inputs["wikidata_countries"])
        self.data, self.report, self.articles = build(inputs, ROOT / "fuentes", "2026-01-01")

    def test_fixture_data_is_up_to_date(self):
        """pruebas/datos must be rebuilt (python -m generador --fixture) when the generator changes."""
        folder = ROOT / "pruebas" / "datos"
        self.assertEqual((folder / "territorios.json").read_text(encoding="utf-8"), exportar.territories_json(self.data))
        self.assertEqual(exportar.check(folder), [])

    def test_report_lists_discrepancies(self):
        sections = self.report.sections
        self.assertIn("08184: varios elementos Q9000018, Q9000019; no se enlaza", sections["Wikidata: código INE"])
        self.assertTrue(any("Q9000003" in m for m in sections["Wikidata: elemento compartido"]))
        self.assertTrue(any("es:provincia:32" in m for m in sections["INE: provincias"]))
        self.assertIn("es:municipio:28079: OSM 5326784, 999", sections["Wikidata: varios valores"])
        self.assertTrue(any("ES111, su provincia ES114" in m for m in sections["Eurostat LAU"]))
        self.assertIn("osm:relation 340138 en es:municipio:17079, es:municipio:32054; no se usa en ninguno",
                      sections["Wikidata: código repetido"])

    def test_dissolved_items_and_counts(self):
        by_id = {t["id"]: t for t in self.data["territories"]}
        self.assertEqual(by_id["es:municipio:36038"]["codes"]["wikidata"], "Q9000017")
        self.assertNotIn("pais:CS", by_id)
        self.assertEqual(sum(t["level"] == "province" for t in self.data["territories"]), 52)
        self.assertEqual(by_id["es:autonomia:05"]["time_zone"], "Atlantic/Canary")
        self.assertEqual(by_id["es:municipio:51001"]["time_zone"], "Africa/Ceuta")
        self.assertTrue(by_id["pais:NO"]["eea"] and not by_id["pais:NO"]["eu"])
        self.assertNotIn("eu", by_id["pais:CH"])


class HandLists(unittest.TestCase):
    def test_every_community_has_names_in_every_interface_language(self):
        import csv
        with (ROOT / "fuentes" / "nombres-comunidades.csv").open(encoding="utf-8") as file:
            rows = list(csv.DictReader(file))
        pairs = {(r["ine"], r["lang"]) for r in rows if r["name"]}
        self.assertEqual(len(pairs), 19 * 6)


if __name__ == "__main__":
    unittest.main()
