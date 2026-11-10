"""Generator: readers and the build on the fixture inputs (pruebas/fuentes/entrada.json)."""
import gzip
import io
import json
import unittest
import zipfile
from pathlib import Path
from zipfile import ZipFile

from pruebas import ROOT
from generador import catastro, eurostat, exportar, ign, ine, limites, wikidata
from generador.construir import build, catastro_name_matches
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

    def test_catastro(self):
        # Same shape as the OVCCallejero answers (seen on 2026-11-09); the values are invented.
        ns = 'xmlns="http://www.catastro.meh.es/"'
        provinces = (f'<consulta_provinciero {ns}><control><cuprov>2</cuprov></control><provinciero>'
                     '<prov><cpine>15</cpine><np>A CORUÑA</np></prov><prov><cpine>03</cpine><np>ALACANT</np></prov>'
                     '</provinciero></consulta_provinciero>').encode()
        self.assertEqual(catastro.parse_provinces(provinces), [["03", "ALACANT"], ["15", "A CORUÑA"]])
        muni = ('<muni><nm>{}</nm><locat><cd>15</cd><cmc>{}</cmc></locat>'
                '<loine><cp>15</cp><cm>{}</cm></loine></muni>')
        answer = (f'<consulta_municipiero {ns}><control><cumun>{{}}</cumun></control><municipiero>'
                  + muni.format("A BAÑA", "7", "7") + muni.format("A CORUÑA", "900", "30")
                  + '</municipiero></consulta_municipiero>')
        self.assertEqual(catastro.parse_municipalities(answer.format(2).encode()),
                         [["15007", "15007", "A BAÑA"], ["15900", "15030", "A CORUÑA"]])
        self.assertRaises(ValueError, catastro.parse_municipalities, answer.format(3).encode())
        error = (f'<consulta_municipiero {ns}><control><cuerr>1</cuerr></control><lerr><err><cod>1</cod>'
                 '<des>LA PROVINCIA NO EXISTE</des></err></lerr></consulta_municipiero>').encode()
        self.assertRaisesRegex(ValueError, "NO EXISTE", catastro.parse_municipalities, error)
        self.assertRaises(ValueError, catastro.parse_municipalities, b"<html>")
        self.assertRaises(ValueError, catastro.parse_municipalities, provinces)
        self.assertEqual(catastro.municipalities_url("A CORUÑA"),
                         catastro.SERVICE + "/ConsultaMunicipio?Provincia=A%20CORU%C3%91A&Municipio=")

    def test_ign_populations(self):
        # Same shape as the IGN features API (collection nuc, seen on 2026-11-09); values invented.
        def page(features, matched=3):
            return json.dumps({"numberMatched": matched, "features": [
                {"type": "Feature", "geometry": None, "properties": p} for p in features]}).encode()
        rows, matched = ign.parse_populations(page([
            {"codine": "32054000101", "nombre": "Ourense", "capital": "001100", "longitud": -7.86, "latitud": 42.33, "altitud": 136.24},
            {"codine": "32054000201", "nombre": "Aldea", "capital": "000000", "longitud": -7.8, "latitud": 42.3, "altitud": None},
            {"codine": "28079000101", "nombre": "Madrid", "capital": "111100", "longitud": -3.7, "latitud": 40.4, "altitud": 657}]))
        self.assertEqual(matched, 3)
        self.assertEqual(ign.municipal_capitals(rows), [["28079", "28079000101", "Madrid", -3.7, 40.4, 657.0],
                                                        ["32054", "32054000101", "Ourense", -7.86, 42.33, 136.2]])
        self.assertRaises(ValueError, ign.parse_populations, page([{"codine": "3205", "capital": "0011"}]))
        self.assertRaises(ValueError, ign.parse_populations, page([{"codine": "32054000101", "capital": "0011"}]))
        self.assertRaises(ValueError, ign.parse_populations, b"<html>")
        self.assertIn("skipGeometry=true", ign.populations_url(5000))
        self.assertIn("offset=5000", ign.populations_url(5000))

    def test_ign_units(self):
        # Same shape as au_AdministrativeUnit_4thOrder0.gml in the BDLJE zip (seen on 2026-11-09).
        gml = """<?xml version='1.0' encoding='UTF-8'?>
<wfs:FeatureCollection xmlns:wfs="http://www.opengis.net/wfs/2.0" xmlns:gml="http://www.opengis.net/gml/3.2">
 <wfs:member><au:AdministrativeUnit xmlns:au="http://inspire.ec.europa.eu/schemas/au/4.0" gml:id="X">
  <au:geometry><gml:MultiSurface><gml:surfaceMember><gml:Polygon>
   <gml:exterior><gml:LinearRing><gml:posList>40 1 40 2 41 2 41 1 40 1</gml:posList></gml:LinearRing></gml:exterior>
   <gml:interior><gml:LinearRing><gml:posList>40.4 1.4 40.4 1.6 40.6 1.6 40.4 1.4</gml:posList></gml:LinearRing></gml:interior>
  </gml:Polygon></gml:surfaceMember></gml:MultiSurface></au:geometry>
  <au:nationalCode>34100303075</au:nationalCode>
  <au:nationalLevelName><gmd:LocalisedCharacterString xmlns:gmd="http://www.isotc211.org/2005/gmd">Municipio</gmd:LocalisedCharacterString></au:nationalLevelName>
  <au:name><gn:GeographicalName xmlns:gn="http://inspire.ec.europa.eu/schemas/gn/4.0"><gn:spelling><gn:SpellingOfName>
   <gn:text>el Castell de Guadalest</gn:text></gn:SpellingOfName></gn:spelling></gn:GeographicalName></au:name>
 </au:AdministrativeUnit></wfs:member>
</wfs:FeatureCollection>"""
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("au_AdministrativeUnit_4thOrder0.gml", gml)
            archive.writestr("au_AdministrativeUnit_3rdOrder0.gml", "<x/>")
        [[code, kind, name, polygons]] = ign.parse_units(buffer.getvalue())
        self.assertEqual((code, kind, name), ("34100303075", "Municipio", "el Castell de Guadalest"))
        self.assertEqual(list(polygons[0][0]), [1, 40, 2, 40, 2, 41, 1, 41, 1, 40])  # lon, lat
        self.assertEqual(len(polygons[0]), 2)
        self.assertRaises(ValueError, ign.parse_units, b"not a zip")
        self.assertRaises(ValueError, ign.check_zip, b"<html>")

    def test_simplify(self):
        from territorios_es import geo
        # 1 m of noise on a 1 km side disappears with a 5 m tolerance; a tiny ring is kept as it is.
        side = [0, 0, 0.005, 0.000009, 0.01, 0, 0.01, 0.01, 0, 0.01, 0, 0]
        self.assertEqual(geo.simplify_ring(side, 5), [0, 0, 0.01, 0, 0.01, 0.01, 0, 0.01, 0, 0])
        self.assertEqual(geo.simplify_ring(side, 0.5), side)
        tiny = [0, 0, 0.00001, 0, 0.00001, 0.00001, 0.000005, 0.000012, 0, 0.00001, 0, 0]
        self.assertEqual(geo.simplify_ring(tiny, 5), tiny)

    def test_limits_file(self):
        square = [0, 0, 0.5, 0.00001, 1, 0, 1, 1, 0, 1, 0, 0]
        units = [["34100303075", "Municipio", "el Castell de Guadalest", [[square]]],
                 ["34151531999", "Condominio", "Zona común", [[square]]]]
        data = {"reference_date": "2026-01-01",
                "territories": [{"id": "es:municipio:03075", "codes": {"ign:bddae": "34100303075"}}]}
        content, counts = limites.build_limits(units, data, {"url": "u"})
        collection = json.loads(gzip.decompress(content))
        self.assertEqual(collection["attribution"], "Obra derivada de BDLJE Continua CC-BY 4.0 ign.es")
        first, second = collection["features"]
        self.assertEqual(first["id"], "es:municipio:03075")
        self.assertNotIn("id", second)
        self.assertEqual(second["properties"], {"bddae": "34151531999", "kind": "Condominio", "name": "Zona común"})
        self.assertEqual(first["geometry"]["coordinates"], [[[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]])
        self.assertEqual((counts["points_before"], counts["points_after"]), (12, 10))

    def test_catastro_names(self):
        """Real names from the first generation (2026-11-09): cut at 30 characters, article at the
        end or missing are the same name; an old or shortened name is not."""
        from territorios_es.text import display_name

        def names(official, parts=None):
            return {"official": official, "display": display_name(official), **({"parts": parts} if parts else {})}
        same = [("BENITACHELL/EL POBLE NOU DE BE", names("Poble Nou de Benitatxell, el/Benitachell",
                                                         {"ca": "el Poble Nou de Benitatxell", "es": "Benitachell"})),
                ("TORREMANZANAS/LA TORRE DE LES", names("Torre de les Maçanes, la/Torremanzanas",
                                                        {"ca": "la Torre de les Maçanes", "es": "Torremanzanas"})),
                ("COVES DE VINROMA LES", names("Coves de Vinromà, les")), ("BLAZQUEZ", names("Blázquez, Los")),
                ("PUEBLA DE ALFINDEN, LA", names("Puebla de Alfindén, La")), ("A CORUÑA", names("Coruña, A")),
                ("MANJABALAGO Y ORTIGOSA DE RIOA", names("Manjabálago y Ortigosa de Rioalmar"))]
        different = [("LA BISBAL DE FALSET", names("Bisbal de Montsant, La")), ("MAO-MAHON", names("Maó")),
                     ("CARBALLEDA", names("Carballeda de Valdeorras")),
                     ("LOS POZUELOS DE CVA", names("Pozuelos de Calatrava, Los"))]
        for dgc_name, known in same:
            self.assertTrue(catastro_name_matches(dgc_name, known), dgc_name)
        for dgc_name, known in different:
            self.assertFalse(catastro_name_matches(dgc_name, known), dgc_name)

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
        self.assertNotIn("VALUES", queries["spain_codes"])
        with_islands = wikidata.queries(["Q8828", "Q40846"])
        for key in ("spain_codes", "spain_labels_ca", "spain_articles_en"):
            self.assertIn("{ VALUES ?item { wd:Q8828 wd:Q40846 } }", with_islands[key])
        self.assertNotIn("VALUES", with_islands["country_codes"])


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
        self.assertIn("es:municipio:46171 «Montcada/Moncada»: an «Sevilla» es también es:municipio:41091",
                      sections["Wikidata: nombre de otro municipio"])
        self.assertIn("15026 «CESURAS» (INE 15026)", sections["Catastro: no está en el INE"])
        self.assertIn("es:municipio:28079: varios códigos DGC (28900, 28901); no se enlaza", sections["Catastro"])
        self.assertIn("Código DGC 41900 en es:municipio:41091, es:municipio:46250; no se usa en ninguno",
                      sections["Catastro"])
        self.assertIn("es:provincia:52 no está en el Catastro", sections["Catastro"])
        self.assertIn("es:municipio:38038 «Santa Cruz de Tenerife» no está en el Catastro", sections["Catastro"])
        self.assertEqual(sections["Catastro: nombre distinto"],
                         ["es:municipio:08101 «L'Hospitalet de Llobregat»: «HOSPITALET» (08102)"])
        self.assertIn("es:provincia:51: 1 municipio(s) con la delegación 55 del Catastro", sections["Notas"])
        self.assertEqual(sections["IGN: capital fuera del término"], [
            "es:municipio:28079 «Madrid»: «Madrid» (28079000101) a 68783 m del límite",
            "es:municipio:32054 «Ourense»: «Ourense» (32054000101) a 823 m del límite"])  # in a hole
        self.assertIn("15026000101 «Cesuras» es capital de 15026, que no está en el INE", sections["IGN: capitales"])
        self.assertIn("es:municipio:36038: varias capitales (36038000101, 36038009901); no se usa ninguna",
                      sections["IGN: capitales"])
        self.assertIn("34151531999 «Zona común inventada» (Condominio) no es un municipio del INE", sections["IGN: límites"])
        self.assertIn("es:municipio:03014: la unidad 34030303014 no es de la comunidad 10; no se enlaza",
                      sections["IGN: límites"])
        self.assertEqual(sections["IGN: nombre distinto"],
                         ["es:municipio:08101 «L'Hospitalet de Llobregat»: «Hospitalet» (34090808101)"])

    def test_ign_codes_and_capitals(self):
        by_id = {t["id"]: t for t in self.data["territories"]}
        self.assertEqual(by_id["es:municipio:15030"]["codes"]["ign:bddae"], "34121515030")
        self.assertEqual(by_id["es:municipio:15030"]["capital"],
                         {"name": "A Coruña", "ine": "15030000101", "lon": -8.4, "lat": 43.36, "altitude": 20.5})
        self.assertEqual(by_id["es:municipio:03139"]["codes"]["ign:bddae"], "34100303139")  # bilingual name
        self.assertNotIn("ign:bddae", by_id["es:municipio:03014"]["codes"])
        self.assertNotIn("capital", by_id["es:municipio:36038"])

    def test_catastro_codes(self):
        dgc = {t["id"]: t["codes"].get("dgc:municipio") for t in self.data["territories"]}
        self.assertEqual(dgc["es:municipio:15030"], "15900")
        self.assertEqual(dgc["es:municipio:03014"], "03015")
        self.assertIsNone(dgc["es:municipio:28079"])
        self.assertIsNone(dgc["es:municipio:41091"])
        self.assertIsNone(dgc["es:municipio:31201"])  # Navarra: foral cadastre
        self.assertEqual(dgc["es:municipio:51001"], "55101")  # Ceuta: Catastro office 55

    def test_dissolved_items_and_counts(self):
        by_id = {t["id"]: t for t in self.data["territories"]}
        self.assertEqual(by_id["es:municipio:36038"]["codes"]["wikidata"], "Q9000017")
        self.assertNotIn("pais:CS", by_id)
        self.assertEqual(sum(t["level"] == "province" for t in self.data["territories"]), 52)
        self.assertEqual(by_id["es:autonomia:05"]["time_zone"], "Atlantic/Canary")
        self.assertEqual(by_id["es:municipio:51001"]["time_zone"], "Africa/Ceuta")
        self.assertTrue(by_id["pais:NO"]["eea"] and not by_id["pais:NO"]["eu"])
        self.assertNotIn("eu", by_id["pais:CH"])


    def test_islands(self):
        by_id = {t["id"]: t for t in self.data["territories"]}
        self.assertEqual(sum(t["level"] == "island" for t in by_id.values()), 11)
        # One NUTS 3 for Eivissa y Formentera: the list in fuentes/islas.csv splits it, and that
        # NUTS 3 is a code of neither island.
        self.assertEqual(by_id["es:municipio:07024"]["island"], "es:isla:formentera")
        self.assertEqual(by_id["es:municipio:07026"]["island"], "es:isla:eivissa")
        self.assertNotIn("nuts", by_id["es:isla:eivissa"]["codes"])
        self.assertEqual(by_id["es:isla:tenerife"]["codes"]["nuts"], "ES709")
        self.assertEqual(by_id["es:municipio:38038"]["parent"], "es:provincia:38")  # unchanged
        self.assertNotIn("island", by_id["es:municipio:36038"])
        self.assertEqual(by_id["es:isla:eivissa"]["names"]["lang"], {"en": "Ibiza", "es": "Ibiza"})
        self.assertIn("es:isla:menorca sin municipios", self.report.sections["Islas"])
        self.assertIn("es:isla:mallorca (Q8828)", self.report.sections["Wikidata: sin elemento"])

    def test_island_list_errors(self):
        import shutil
        import tempfile
        inputs = json.loads((ROOT / "pruebas" / "fuentes" / "entrada.json").read_text(encoding="utf-8"))
        inputs["wikidata_spain"] = wikidata.from_jsonable(inputs["wikidata_spain"])
        inputs["wikidata_countries"] = wikidata.from_jsonable(inputs["wikidata_countries"])
        with tempfile.TemporaryDirectory() as folder:
            shutil.copytree(ROOT / "fuentes", folder, dirs_exist_ok=True)
            path = Path(folder) / "islas.csv"
            original = path.read_text(encoding="utf-8")
            # A listed municipality whose NUTS 3 is another island's, and one the INE does not have.
            path.write_text(original.replace("Q8828,", "Q8828,07026 07999"), encoding="utf-8")
            _, report, _ = build(inputs, Path(folder), "2026-01-01")
            self.assertIn("es:municipio:07026 «Eivissa»: en fuentes/islas.csv con es:isla:mallorca, pero su "
                          "NUTS 3 es ES531", report.sections["Islas"])
            self.assertIn("07999 está en fuentes/islas.csv (es:isla:mallorca) pero no en el INE",
                          report.sections["Islas"])
            self.assertIn("es:municipio:07040 «Palma» sin isla (NUTS 3 ES532)", report.sections["Islas"])
            for broken, message in (("es:isla:tenerife,38", "es:isla:tenerife,36"),  # not an island province
                                    ("Q40846", "40846"),  # not a QID
                                    ("Q52636,", "Q52636,07024")):  # listed twice
                path.write_text(original.replace(broken, message), encoding="utf-8")
                with self.assertRaises(ValueError):
                    build(inputs, Path(folder), "2026-01-01")


class HandLists(unittest.TestCase):
    def test_every_community_has_names_in_every_interface_language(self):
        import csv
        with (ROOT / "fuentes" / "nombres-comunidades.csv").open(encoding="utf-8") as file:
            rows = list(csv.DictReader(file))
        pairs = {(r["ine"], r["lang"]) for r in rows if r["name"]}
        self.assertEqual(len(pairs), 19 * 6)


if __name__ == "__main__":
    unittest.main()
