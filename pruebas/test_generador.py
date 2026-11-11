"""Generator: readers and the build on the fixture inputs (pruebas/fuentes/entrada.json)."""
import gzip
import io
import json
import unittest
import zipfile
from collections import Counter
from pathlib import Path
from zipfile import ZipFile

from pruebas import ROOT
from generador import catastro, codigos_postales, eurostat, exportar, ign, ine, limites, wikidata
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

    def test_ine_islands(self):
        sheet = lambda title, rows: [[title], ["Illes Balears"], ["CPRO", "CISLA", "ISLA", "CMUN", "DC", "NOMBRE"], *rows]
        title = "Relación de municipios y códigos por provincia e islas a 1 de enero de 2025"
        content = xlsx({"07": sheet(title, [["07", "072", "Ibiza", "026", "0", "Eivissa"],
                                            ["07", "071", "Formentera", "024", "4", "Formentera"]]),
                        "38": sheet(title, [["38", "381", "Gomera, La ", "002", "7", "Agulo"]])})
        self.assertEqual(ine.parse_islands(content), ([["071", "Formentera", "07024", "4"], ["072", "Ibiza", "07026", "0"],
                                                       ["381", "Gomera, La", "38002", "7"]], "2025-01-01"))
        for row in (["07", "381", "Ibiza", "026", "0", "Eivissa"],  # island of another province
                    ["07", "072", "Ibiza", "26", "0", "Eivissa"]):  # short code
            self.assertRaises(ValueError, ine.parse_islands, xlsx({"07": sheet(title, [row])}))
        self.assertRaises(ValueError, ine.parse_islands, xlsx({"07": [["Sin cabecera"]]}))

    def test_ine_population(self):
        tables = [{"Id": 2855, "Nombre": "Albacete: Población por municipios y sexo.", "Codigo": "PROV-MUN"},
                  {"Id": 2854, "Nombre": "Araba/Álava: Población por municipios y sexo. ", "Codigo": "PROV-MUN"},
                  {"Id": 2853, "Nombre": "Población por comunidades y ciudades autónomas y sexo.", "Codigo": "NAC-CCAA"}]
        self.assertEqual(ine.population_tables(json.dumps(tables).encode(), "PROV-MUN"), [2854, 2855])
        self.assertRaises(ValueError, ine.population_tables, b"[]", "PROV-MUN")
        self.assertRaises(ValueError, ine.population_tables, b"<html>", "PROV-MUN")

        # Shape of DATOS_TABLA/2854?nult=1&tip=AM (seen on 2026-11-10).
        def series(variable, name, code, sex, value, date="2025-01-01T00:00:00.000+01:00"):
            return {"COD": "DPOP7", "Nombre": f"{name}. Total. Total habitantes. Personas. ",
                    "MetaData": [{"Id": 6080, "T3_Variable": variable, "Nombre": name, "Codigo": code},
                                 {"Id": 451 + int(sex), "T3_Variable": "Sexo", "Nombre": "Total", "Codigo": sex},
                                 {"Id": 8677, "T3_Variable": "Tamaño de los municipios", "Nombre": "Total habitantes",
                                  "Codigo": "0"}],
                    "Data": [{"Fecha": date, "T3_TipoDato": "Definitivo", "T3_Periodo": "A", "Anyo": 2025,
                              "Valor": value}]}
        table = [series("Provincias", "Araba/Álava", "01", "0", 342161.0),
                 series("Provincias", "Araba/Álava", "01", "1", 168459.0),
                 series("Municipios", "Alegría-Dulantzi", "01001", "0", 2955.0),
                 series("Municipios", "Alegría-Dulantzi", "01001", "2", 1500.0),
                 series("Municipios", "Vitoria-Gasteiz", "01059", "0", 260699.0)]
        gone = series("Municipios", "Cesuras", "01026", "0", 1.0)
        gone["Data"] = []  # a municipality that no longer exists (seen in A Coruña on 2026-11-10)
        table.append(gone)
        self.assertEqual(ine.parse_population(json.dumps(table).encode()),
                         ({"01": 342161, "01001": 2955, "01059": 260699}, "2025-01-01"))
        for broken in ([*table, series("Municipios", "Burgos", "09059", "0", 1.0)],  # another province
                       [*table, series("Provincias", "Burgos", "09", "0", 1.0)],
                       table[2:],  # no province total
                       [*table, series("Municipios", "Vitoria-Gasteiz", "01059", "0", 1.0)],  # repeated
                       [*table, series("Municipios", "Otro", "01902", "0", None)],  # no value
                       [*table, series("Municipios", "Otro", "01902", "0", 1.0, "2024-01-01T00:00:00.000+01:00")]):
            self.assertRaises(ValueError, ine.parse_population, json.dumps(broken).encode())
        self.assertRaises(ValueError, ine.parse_population, b'{"status": "error"}')
        self.assertRaises(ValueError, ine.parse_population, b"<html>")

    def test_ine_changes_html(self):
        def page(*rows):
            body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>" for row in rows)
            return ("<html><head><meta charset=ISO-8859-15></head><body>Modificaciones en los municipios producidas "
                    f"desde el 01-01-2026<table>{body}</table></body></html>").encode("iso-8859-15")
        content = page(["Relaci&oacute;n de municipios creados"],
                       ["Provincia", "C&oacute;digo", "Denominaci&oacute;n", "Municipio del que se segrega", "Fecha"],
                       ["Coruña, A", "15 902 7", "Oza-Cesuras", "15 026 9", "02/06/2013", "06/06/2013"],
                       ["", "", "", "15 063 9", "Oza dos Ríos"],
                       ["Cambio de denominaci&oacute;n de los municipios"],
                       ["Provincia", "Denominación nueva", "Código", "Denominación anterior", "Fecha"],
                       ["Pontevedra", "Caniza, A", "36 009 7", "Cañiza, A", "15/06/2026"],
                       ["Corrección en la denominación de los municipios"],
                       ["Provincia", "Denominación corregida", "Código", "Denominación anterior"],
                       ["Jaén", "Espeluy", "23 032 0", "Espelúy"])
        since, changes = ine.parse_changes(content)
        self.assertEqual(since, "2026-01-01")
        self.assertEqual(changes, [
            {"kind": "created", "code": "15902", "check": "7", "name": "Oza-Cesuras",
             "other": "15 026 9; 15 063 9 Oza dos Ríos", "date": "2013-06-02"},
            {"kind": "renamed", "code": "36009", "check": "7", "name": "Caniza, A", "previous": "Cañiza, A",
             "date": "2026-06-15"},
            {"kind": "corrected", "code": "23032", "check": "0", "name": "Espeluy", "previous": "Espelúy", "date": None}])
        self.assertEqual(ine.parse_changes(page(["Cambio de denominación"], ["Provincia", "Nueva", "Código"])),
                         ("2026-01-01", []))

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
        self.assertIn("/collections/nuc/items?", ign.populations_url(0))
        self.assertNotIn("capital=", ign.populations_url(0))
        self.assertIn("/collections/opob/items?", ign.populations_url(0, other=True))
        self.assertIn("capital=000100", ign.populations_url(0, other=True))
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
        self.assertEqual(sorted(i for i in by_id if i.startswith("es:isla:")),
                         ["es:isla:071", "es:isla:072", "es:isla:073", "es:isla:352", "es:isla:384"])
        # Code, name and municipalities from the INE; Eivissa y Formentera share one NUTS 3, which
        # is then a code of neither island.
        self.assertEqual(by_id["es:municipio:07024"]["island"], "es:isla:071")
        self.assertEqual(by_id["es:municipio:07026"]["island"], "es:isla:072")
        self.assertEqual(by_id["es:isla:072"]["codes"], {"ine:isla": "072", "wikidata": "Q52631"})
        self.assertEqual(by_id["es:isla:384"]["codes"]["nuts"], "ES709")
        self.assertEqual(by_id["es:isla:072"]["names"], {"official": "Ibiza", "display": "Ibiza", "lang": {"ca": "Eivissa"}})
        self.assertEqual(by_id["es:municipio:38038"]["parent"], "es:provincia:38")  # unchanged
        self.assertNotIn("island", by_id["es:municipio:36038"])
        self.assertIn("074 está en fuentes/islas.csv pero no en la tabla de islas del INE", self.report.sections["Islas"])
        self.assertIn("es:isla:073 «Mallorca» (Q8828)", self.report.sections["Wikidata: sin elemento"])

    def test_population(self):
        by_id = {t["id"]: t for t in self.data["territories"]}
        self.assertEqual(by_id["es:municipio:28079"]["stats"], {"population": 3422416, "area_km2": 12.346})
        self.assertEqual(by_id["es:provincia:36"]["stats"], {"population": 85000})
        self.assertNotIn("stats", by_id["es:provincia:02"])
        self.assertNotIn("stats", by_id["es:municipio:04078"])  # in neither the INE nor the LAU table
        self.assertNotIn("stats", by_id["es:autonomia:12"])
        self.assertEqual(self.report.sections["INE: población"], [
            "es:municipio:04078 «Rioja» sin población del INE",
            "Provincias sin población del INE: 02, 04, 05, 06, 09, 10, 11, 13, 14, 16, 18, 19, 21, 22, 23, 24, 27, 29, "
            "30, 34, 37, 39, 40, 42, 43, 44, 45, 47, 49",
            "28999: población del INE (5) de un municipio que no está en el diccionario",
            "es:provincia:41: sus municipios suman 684025 y el total del INE es 684026"])

    def test_name_changes_of_the_year(self):
        by_id = {t["id"]: t for t in self.data["territories"]}
        cangas = by_id["es:municipio:36008"]["names"]
        self.assertEqual((cangas["official"], cangas["display"]), ("Cangas de Morrazo", "Cangas de Morrazo"))
        self.assertIn({"name": "Cangas", "lang": None, "kind": "former_official", "source": "ine",
                       "until": "2026-06-15"}, cangas["aliases"])
        self.assertIn("es:municipio:36008: «Cangas» → «Cangas de Morrazo» (REL, 2026-06-15)",
                      self.report.sections["INE: nombres nuevos"])
        self.assertIn("15903 «Concello novo» creado el 2026-09-01 (15 030 8 Coruña, A); entrará con el diccionario del "
                      "año siguiente", self.report.sections["INE: cambios del año"])
        inputs = json.loads((ROOT / "pruebas" / "fuentes" / "entrada.json").read_text(encoding="utf-8"))
        inputs["wikidata_spain"] = wikidata.from_jsonable(inputs["wikidata_spain"])
        inputs["wikidata_countries"] = wikidata.from_jsonable(inputs["wikidata_countries"])
        inputs["ine_changes"]["changes"] = [
            {"kind": "renamed", "code": "36038", "check": "1", "name": "Pontevedra nova", "previous": "Pontevedra vella",
             "date": None},
            {"kind": "renamed", "code": "36999", "check": "0", "name": "Ningún", "previous": "Ninguno", "date": None}]
        data, report, _ = build(inputs, ROOT / "fuentes", "2026-01-01")
        changes = report.sections["INE: cambios del año"]
        self.assertIn("es:municipio:36038: el cambio de «Pontevedra vella» a «Pontevedra nova» no parte de «Pontevedra»; "
                      "no se aplica", changes)
        self.assertIn("es:municipio:36038: dígito de control 1 en la página de cambios, 8 en el diccionario", changes)
        self.assertIn("36999 «Ningún» (antes «Ninguno») no está en el diccionario", changes)
        self.assertEqual({t["id"]: t for t in data["territories"]}["es:municipio:36008"]["names"]["official"], "Cangas")
        inputs["ine_changes"]["since"] = "2027-01-01"
        _, report, _ = build(inputs, ROOT / "fuentes", "2026-01-01")
        self.assertIn("La página de cambios empieza el 2027-01-01 y el diccionario es del 2026-01-01: no se aplica",
                      report.sections["INE: cambios del año"])
        inputs["ine_changes"] = None
        _, report, _ = build(inputs, ROOT / "fuentes", "2026-01-01")
        self.assertEqual(len(report.sections["INE: cambios del año"]), 1)

    def test_island_table_errors(self):
        inputs = json.loads((ROOT / "pruebas" / "fuentes" / "entrada.json").read_text(encoding="utf-8"))
        inputs["wikidata_spain"] = wikidata.from_jsonable(inputs["wikidata_spain"])
        inputs["wikidata_countries"] = wikidata.from_jsonable(inputs["wikidata_countries"])
        rows = inputs["ine_islands"]
        inputs["ine_islands"] = [r for r in rows if r[2] != "35016"] + [
            ["073", "Mallorca", "07026", "9"],  # another island than its NUTS 3, and another check digit
            ["074", "Menorca", "07999", "1"]]  # not in the dictionary
        inputs["ine_islands"] = [r for r in inputs["ine_islands"] if r[:3] != ["072", "Ibiza", "07026"]]
        _, report, _ = build(inputs, ROOT / "fuentes", "2026-01-01")
        islands = report.sections["Islas"]
        self.assertIn("es:municipio:07026 «Eivissa»: dígito de control 9 en la tabla de islas, 0 en el diccionario", islands)
        self.assertIn("es:municipio:07026 «Eivissa»: en es:isla:073 según el INE, pero su NUTS 3 es ES531 y el de la "
                      "isla ES532", islands)
        self.assertIn("07999 está en la tabla de islas del INE (es:isla:074) pero no en el diccionario de municipios",
                      islands)
        self.assertIn("es:municipio:35016 «Las Palmas de Gran Canaria» no está en la tabla de islas del INE", islands)
        for broken in ([["071", "Formentera", "07024", "4"], ["071", "Formentera bis", "07026", "0"]],  # two names
                       [["361", "Ons", "36038", "8"]]):  # Pontevedra is not split into islands
            inputs["ine_islands"] = broken
            with self.assertRaises(ValueError):
                build(inputs, ROOT / "fuentes", "2026-01-01")


def zipped(files: dict[str, bytes]) -> bytes:
    out = io.BytesIO()
    with ZipFile(out, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return out.getvalue()


def catastro_gml(addresses: list[tuple[str, str]], descriptors: dict[str, str]) -> bytes:
    """INSPIRE AD GML in the shape of the Catastro files (seen on 2026-11-10); values invented.
    `addresses` are (descriptor id or "", unit id); descriptors come after the addresses, as there."""
    members = []
    for i, (descriptor, unit) in enumerate(addresses):
        links = (f'<AD:component xlink:href="#{descriptor}" />' if descriptor else "") + \
                '<AD:component xlink:href="#ES.SDGC.TN.02.001.1" />' + f'<AD:component xlink:href="#{unit}" />'
        members.append(f'<gml:featureMember><AD:Address gml:id="ES.SDGC.AD.{i}"><AD:inspireId><base:Identifier>'
                       f'<base:localId>{i}</base:localId></base:Identifier></AD:inspireId>{links}</AD:Address>'
                       '</gml:featureMember>')
    for identity, code in descriptors.items():
        members.append(f'<gml:featureMember><AD:PostalDescriptor gml:id="{identity}"><AD:postName><GN:GeographicalName>'
                       f'<GN:text /></GN:GeographicalName></AD:postName><AD:postCode>{code}</AD:postCode>'
                       '</AD:PostalDescriptor></gml:featureMember>')
    gml = ('<?xml version="1.0" encoding="ISO-8859-1"?><gml:FeatureCollection gml:id="ES.SDGC.AD" '
           'xmlns:GN="urn:x-inspire:specification:gmlas:GeographicalNames:3.0" '
           'xmlns:base="urn:x-inspire:specification:gmlas:BaseTypes:3.2" xmlns:gml="http://www.opengis.net/gml/3.2" '
           'xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:AD="urn:x-inspire:specification:gmlas:Addresses:3.0">'
           + "".join(members) + "</gml:FeatureCollection>")
    return zipped({"A.ES.SDGC.AD.02900.gml": gml.encode("iso-8859-1"), "A.ES.SDGC.AD.MD.02900.xml": b"<md/>"})


def dbf(fields: list[tuple[str, int]], records: list[tuple[bool, list[str]]]) -> bytes:
    """Minimal dBASE III file (type C fields), as in the IDENA shapefile; values invented."""
    size = 1 + sum(length for _, length in fields)
    header = 32 + 32 * len(fields) + 1
    out = bytearray(b"\x03\x7e\x0a\x02" + len(records).to_bytes(4, "little") + header.to_bytes(2, "little")
                    + size.to_bytes(2, "little") + bytes(20))
    for name, length in fields:
        out += name.encode().ljust(11, b"\0") + b"C" + bytes(4) + bytes([length, 0]) + bytes(14)
    out += b"\r"
    for deleted, values in records:
        out += b"*" if deleted else b" "
        for (_, length), value in zip(fields, values):
            out += value.encode("cp1252").ljust(length)[:length]
    return bytes(out + b"\x1a")


def prefixed_xlsx(rows: list[list[str]]) -> bytes:
    """XLSX with the x: prefix and shared strings, as Eustat writes it."""
    main = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    strings = sorted({v for row in rows for v in row if v})
    cells = "".join(
        f'<x:row r="{r}">' + "".join(f'<x:c r="{chr(65 + c)}{r}" t="s"><x:v>{strings.index(v)}</x:v></x:c>'
                                    for c, v in enumerate(row) if v) + "</x:row>" for r, row in enumerate(rows, 1))
    return zipped({
        "xl/workbook.xml": f'<x:workbook xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
                           f'xmlns:x="{main}"><x:sheets><x:sheet name="Sheet1" sheetId="1" r:id="rId1"/></x:sheets></x:workbook>',
        "xl/_rels/workbook.xml.rels": '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                                      '<Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>',
        "xl/sharedStrings.xml": f'<x:sst xmlns:x="{main}">' + "".join(f"<x:si><x:t>{v}</x:t></x:si>" for v in strings) + "</x:sst>",
        "xl/worksheets/sheet1.xml": f'<x:worksheet xmlns:x="{main}"><x:sheetData>{cells}</x:sheetData></x:worksheet>'})


EUSKADI_HEADER = ["LH Kodea/Código TH", "Lurralde historikoa/Territorio histórico", "Udalerri-kodea/Código Municipio",
                  "Udalerria/Municipio", *[f"c{i}" for i in range(4, 18)], "Posta-kodea/Código Postal",
                  "Posta-helbidea/Dirección postal"]


def euskadi_row(province: str, number: str, code: str) -> list[str]:
    return [province, "Araba/Álava", number, "Inventado", *["x"] * 14, code, "Kalea, 1"]


class PostalCodes(unittest.TestCase):
    def test_postal_code_and_valid(self):
        self.assertEqual(codigos_postales.postal_code(" 2250"), "02250")
        self.assertEqual(codigos_postales.postal_code("28001"), "28001")
        self.assertEqual(codigos_postales.postal_code("0"), "0")
        self.assertEqual(codigos_postales.postal_code(None), "")
        self.assertTrue(codigos_postales.valid("52001"))
        for bad in ("00043", "53001", "2800", "28 01", "0"):
            self.assertFalse(codigos_postales.valid(bad), bad)

    def test_catastro_feeds(self):
        atom = '<feed xmlns="http://www.w3.org/2005/Atom">{}</feed>'
        entry = '<entry><title>{}</title><link rel="enclosure" href="{}" type="application/atom+xml" /></entry>'
        general = atom.format(
            "<updated>2026-08-21T00:00:00Z</updated>"
            + entry.format("Territorial office 02 Albacete",
                           "http://www.catastro.hacienda.gob.es/INSPIRE/addresses/02/ES.SDGC.ad.atom_02.xml")
            + entry.format("", "http://www.catastro.hacienda.gob.es/INSPIRE/addresses/56/ES.SDGC.ad.atom_56.xml")
            + entry.format("Provincial Council of Navarra", "https://filescartografia.navarra.es/AD/Addresses.xml")
        ).encode()
        self.assertEqual(codigos_postales.parse_catastro_feed(general), ["02", "56"])
        self.assertEqual(codigos_postales.feed_updated(general), "2026-08-21")
        self.assertRaises(ValueError, codigos_postales.parse_catastro_feed, atom.format("").encode())
        self.assertEqual(codigos_postales.office_feed_url("02"),
                         "https://www.catastro.hacienda.gob.es/INSPIRE/Addresses/02/ES.SDGC.ad.atom_02.xml")
        base = "https://www.catastro.hacienda.gob.es/INSPIRE/Addresses/02/"
        office = ('<?xml version="1.0" encoding="ISO-8859-1"?>' + atom.format(
            entry.format(" 02024-CASAS IBAÑEZ addresses", base + "02024-CASAS IBAÑEZ/A.ES.SDGC.AD.02024.zip")
            + entry.format(" 02001-ABENGIBRE addresses", base.replace("https", "http") + "02001-ABENGIBRE/A.ES.SDGC.AD.02001.zip")
            + '<entry><link rel="self" href="https://example.org/feed.xml" /></entry>')).encode("iso-8859-1")
        self.assertEqual(codigos_postales.parse_office_feed(office), [
            ["02001", [base + "02001-ABENGIBRE/A.ES.SDGC.AD.02001.zip"]],
            ["02024", [base + "02024-CASAS%20IBA%C3%91EZ/A.ES.SDGC.AD.02024.zip",
                       base + "02024-CASAS%20IBA%D1EZ/A.ES.SDGC.AD.02024.zip"]]])
        self.assertRaises(ValueError, codigos_postales.parse_office_feed, atom.format("").encode())

    def test_catastro_addresses(self):
        unit = "ES.SDGC.AU.02.900"
        content = catastro_gml(
            [("ES.SDGC.PD.02.900.2250", unit)] * 3 + [("ES.SDGC.PD.02.900.02001", unit),
                                                      ("ES.SDGC.PD.02.900.", unit),  # broken link, as in Madrid
                                                      ("", unit)],
            {"ES.SDGC.PD.02.900.2250": "2250", "ES.SDGC.PD.02.900.02001": "02001"})
        self.assertEqual(codigos_postales.parse_catastro_ad(content),
                         {("02250", "02900"): 3, ("02001", "02900"): 1, ("", "02900"): 2})
        self.assertRaises(ValueError, codigos_postales.parse_catastro_ad, content[:100])
        self.assertRaises(ValueError, codigos_postales.parse_catastro_ad, zipped({"a.txt": b"x"}))
        without_unit = catastro_gml([("ES.SDGC.PD.02.900.2250", "ES.SDGC.TN.02.900.1")], {})
        self.assertRaises(ValueError, codigos_postales.parse_catastro_ad, without_unit)
        codigos_postales.check_zip(content)
        self.assertRaises(ValueError, codigos_postales.check_zip, b"<html>")

    def test_navarra(self):
        fields = [("FEATURE", 8), ("CMUNICIPIO", 11), ("MUNICIPIO", 100), ("CODPOSTAL", 50)]
        records = [(False, ["1", "1".rjust(11), "Abáigar", "31280"]), (False, ["2", "201".rjust(11), "Pamplona", "31001"]),
                   (False, ["3", "201".rjust(11), "Pamplona", "31001"]), (True, ["4", "201".rjust(11), "Pamplona", "31002"]),
                   (False, ["5", "35".rjust(11), "Bera", "0"]), (False, ["6", "35".rjust(11), "Bera", ""])]
        content = zipped({"DIRECC_Txt_Direcciones.dbf": dbf(fields, records), "DIRECC_Txt_Direcciones.shp": b""})
        self.assertEqual(codigos_postales.parse_navarra(content),
                         {("31280", "31001"): 1, ("31001", "31201"): 2, ("0", "31035"): 1, ("", "31035"): 1})
        self.assertRaises(ValueError, codigos_postales.parse_navarra, zipped({"a.shp": b""}))
        cut = zipped({"a.dbf": dbf(fields, records)[:-200]})
        self.assertRaises(ValueError, codigos_postales.parse_navarra, cut)
        other = zipped({"a.dbf": dbf([("CMUN", 3), ("CP", 5)], [(False, ["1", "31280"])])})
        self.assertRaises(ValueError, codigos_postales.parse_navarra, other)

    def test_euskadi(self):
        rows = [euskadi_row("01", "059", " 01001"), euskadi_row("01", "059", " 01001"), euskadi_row("1", "1", " 01240")]
        text = "\r\n".join(";".join(r) for r in [EUSKADI_HEADER, *rows]) + "\r\n"
        expected = {("01001", "01059"): 2, ("01240", "01001"): 1}
        self.assertEqual(codigos_postales.parse_euskadi(("﻿" + text).encode("utf-8")), expected)
        self.assertEqual(codigos_postales.parse_euskadi(prefixed_xlsx([EUSKADI_HEADER, *rows])), expected)
        self.assertRaises(ValueError, codigos_postales.parse_euskadi, b"a;b;c\r\n")
        bad = "\r\n".join(";".join(r) for r in [EUSKADI_HEADER, euskadi_row("Araba", "059", "01001")])
        self.assertRaises(ValueError, codigos_postales.parse_euskadi, bad.encode())
        codigos_postales.check_euskadi(("﻿" + text).encode("utf-8"))
        codigos_postales.check_euskadi(prefixed_xlsx([EUSKADI_HEADER]))
        self.assertRaises(ValueError, codigos_postales.check_euskadi, b"<html>")

    def test_icgc(self):
        header = "idadrvia;codmuni;nommuni;codpostal;coor_utmx;coor_utmy"
        via = "\n".join([header, "av1;081038;Jorba;08719;1;2", "av2;081038;Jorba;08719;1;2", "av3;080193;Barcelona;8001;1;2",
                          "av4;080193;Barcelona;-;1;2"])
        edi = "\n".join(["idadredi;codmuni;nommuni;codpostal;coor_utmx;coor_utmy", "ae1;081038;Jorba;08719;1;2"])
        content = zipped({"adreces-simplificat-v1r0-adrecavia-20261009.csv": ("\ufeff" + via).encode(),
                          "adreces-simplificat-v1r0-adrecaedi-20261009.csv": edi.encode(),
                          "adreces-simplificat-v1r0-municipi-20261009.csv": b"codmuni;nommuni\n"})
        self.assertEqual(codigos_postales.parse_icgc(content),
                         {("08719", "08103"): 3, ("08001", "08019"): 1, ("-", "08019"): 1})
        self.assertRaises(ValueError, codigos_postales.parse_icgc, zipped({"a.csv": b"x"}))
        bad = zipped({"x-adrecavia-1.csv": b"codmuni;codpostal\n8103;08719\n", "x-adrecaedi-1.csv": b"codmuni;codpostal\n"})
        self.assertRaises(ValueError, codigos_postales.parse_icgc, bad)

    def test_madrid(self):
        text = "COD_VIA;VIA_CLASE;VIA_NOMBRE;NUMERO;COD_POSTAL;LATITUD\n1;CALLE;ÁLAMO;2;28022;x\n2;AUTOVÍA;A-1;10000;28050;x\n3;CALLE;B;1;28022;x\n"
        self.assertEqual(codigos_postales.parse_madrid(text.encode("cp1252")), {("28022", "28079"): 2, ("28050", "28079"): 1})
        self.assertRaises(ValueError, codigos_postales.parse_madrid, b"COD_VIA;NUMERO\n1;2\n")
        codigos_postales.check_madrid(text.encode("cp1252"))
        self.assertRaises(ValueError, codigos_postales.check_madrid, b"<html>")
        catalogue = json.dumps({"result": {"resources": [
            {"id": "x-1-csv", "url": "https://datos.madrid.es/x/direccionesevolucionhistorica_20261109.csv"},
            {"id": "x-4-csv", "url": "https://datos.madrid.es/x/direccionesvigentes_20261109.csv"}]}}).encode()
        self.assertEqual(codigos_postales.madrid_csv_url(catalogue, "x-4-csv"),
                         "https://datos.madrid.es/x/direccionesvigentes_20261109.csv")
        self.assertRaises(ValueError, codigos_postales.madrid_csv_url, catalogue, "x-9-csv")
        self.assertRaises(ValueError, codigos_postales.madrid_csv_url, b"<html>", "x-4-csv")

    def test_icgc_directory(self):
        base = "https://datacloud.icgc.cat/datacloud/adreces-simplificat/csv/"
        listing = (b'<pre><A HREF="/datacloud/adreces-simplificat/">[To Parent Directory]</A>'
                   b'<A HREF="/datacloud/adreces-simplificat/csv/adreces-simplificat-v1r0-20261009.zip">a</A>'
                   b'<A HREF="/datacloud/adreces-simplificat/csv/adreces-simplificat-v1r0-20260410.zip">b</A></pre>')
        self.assertEqual(codigos_postales.icgc_zip_url(listing, base), base + "adreces-simplificat-v1r0-20261009.zip")
        self.assertRaises(ValueError, codigos_postales.icgc_zip_url, b"<pre></pre>", base)

    def test_cdau(self):
        header = 'id_vial;ine_via;nom_via;num_por_desde;ine_mun;nom_municipio;cod_postal;x;y'
        rows = ['1;"4109100001";"CALLE INVENTADA";5;"41091";"Sevilla";"41001";1;2',
                '2;"4109100001";"CALLE INVENTADA";7;"41091";"Sevilla";"41001";1;2',
                '3;"0400300002";"CALLE INVENTADA";1;"04003";"Abla";"4510";1;2']
        content = zipped({"portal_Andalucia.csv": ("\ufeff" + "\n".join([header, *rows]) + "\n").encode("utf-8")})
        self.assertEqual(codigos_postales.parse_cdau(content), {("41001", "41091"): 2, ("04510", "04003"): 1})
        self.assertRaises(ValueError, codigos_postales.parse_cdau, zipped({"a.txt": b"x"}))
        self.assertRaises(ValueError, codigos_postales.parse_cdau, zipped({"a.csv": b"ine_mun;cp\n41091;41001\n"}))
        bad = zipped({"a.csv": b"ine_mun;cod_postal\n4109;41001\n"})
        self.assertRaises(ValueError, codigos_postales.parse_cdau, bad)

    def test_ideib(self):
        rows = ['"ADRECA_DET"',
                '"CARRER INVENTAT 30  07200 Felanitx Felanitx / INE_VIA:0702200036 / ID_VIAL:70220000357 / ID_PORTAL:70220060079"',
                '"CARRER INVENTAT 13 C 07839 Vista Alegre Sant Josep / INE_VIA:-997 / ID_VIAL:70480000033 / ID_PORTAL:70480003622"',
                '"CARRER INVENTAT 15 C 07839 Vista Alegre Sant Josep / INE_VIA:-997 / ID_VIAL:70480000033 / ID_PORTAL:70480003623"',
                '"PASSEIG INVENTAT 9   Port de Pollença Pollença / INE_VIA:0704200048 / ID_VIAL:70420000380 / ID_PORTAL:70420283755"']
        content = ("\ufeff" + "\r\n".join(rows) + "\r\n").encode("utf-8")
        self.assertEqual(codigos_postales.parse_ideib(content),
                         {("07200", "07022"): 1, ("07839", "07048"): 2, ("", "07042"): 1})
        codigos_postales.check_ideib(content)
        self.assertRaises(ValueError, codigos_postales.check_ideib, b"<html>")
        self.assertRaises(ValueError, codigos_postales.parse_ideib, b"ADRECA;CP\r\n")
        self.assertRaises(ValueError, codigos_postales.parse_ideib, ('"ADRECA_DET"\r\n"CARRER 1  07200 X"\r\n').encode())

    def test_ine_streets(self):
        line = lambda municipality, code: (municipality + "0" * 37 + code + " CALLE INVENTADA").ljust(80) + "\r\n"
        tramos = (line("15030", "15001") + line("15030", "15001") + line("29067", "29620")).encode("cp1252")
        expected = {("15001", "15030"): 2, ("29620", "29067"): 1}
        self.assertEqual(codigos_postales.parse_ine_streets(zipped({"TRAMOS-NAL.F260701": tramos})), expected)
        nested = zipped({"caj_esp_072026/TRAM.zip": zipped({"TRAMOS-NAL.F260701": tramos}), "VIAS-NAL": b""})
        self.assertEqual(codigos_postales.parse_ine_streets(nested), expected)
        self.assertRaises(ValueError, codigos_postales.parse_ine_streets, zipped({"VIAS-NAL": b""}))
        self.assertRaises(ValueError, codigos_postales.parse_ine_streets, zipped({"TRAMOS": b"otra forma\r\n" * 5}))
        template = "https://www.ine.es/prodyser/callejero/caj_esp/caj_esp_{month}{year}.zip"
        self.assertEqual([u[-10:] for u in codigos_postales.ine_street_urls(template, "2026-11-10")],
                         ["072026.zip", "012026.zip", "072025.zip"])
        self.assertEqual([u[-10:] for u in codigos_postales.ine_street_urls(template, "2026-03-01")],
                         ["012026.zip", "072025.zip", "012025.zip"])

    def _data(self):
        town = lambda ine, province, name, dgc=None: {
            "id": f"es:municipio:{ine}", "level": "municipality", "parent": f"es:provincia:{province}",
            "names": {"display": name}, "codes": {"ine:municipio": ine, **({"dgc:municipio": dgc} if dgc else {})}}
        return {"territories": [town("02003", "02", "Albacete", "02900"), town("02001", "02", "Abengibre", "02001"),
                                town("31201", "31", "Pamplona/Iruña", "31900"), town("01059", "01", "Vitoria-Gasteiz"),
                                town("02002", "02", "Sin direcciones", "02002"), town("15902", "15", "Oza-Cesuras"),
                                {"id": "es:provincia:02", "level": "province"}]}

    def test_build(self):
        counts = {"catastro": Counter({("02001", "02900"): 500, ("02002", "02900"): 2, ("02250", "02001"): 2,
                                       ("02250", "02900"): 7, ("", "02900"): 4, ("53001", "02001"): 9,
                                       ("02005", "02999"): 3, ("02000", "02900"): 6, ("31009", "31900"): 4,
                                       ("15680", "15026"): 30, ("15680", "15064"): 12}),
                  "ine": Counter({("02001", "02003"): 40, ("02250", "02003"): 3, ("31001", "31201"): 5,
                                  ("02000", "02003"): 1, ("31009", "31201"): 2}),
                  "idena": Counter({("31001", "31201"): 50, ("02001", "31201"): 3}),
                  "eustat": Counter({("01001", "01059"): 10, ("01001", "31201"): 1})}
        rows, observations, report = codigos_postales.build(counts, self._data())
        self.assertEqual(rows, [
            ["01001", "es:municipio:01059", "01059", "eustat", 10, "portals", ""],
            ["02001", "es:municipio:02003", "02003", "ine", 40, "street_sections", "catastro"],
            ["02001", "es:municipio:31201", "31201", "idena", 3, "addresses", ""],
            # Two units: by the street sections of the INE (Abengibre has none), not by identifier.
            ["02250", "es:municipio:02003", "02003", "ine", 3, "street_sections", "catastro"],
            ["02250", "es:municipio:02001", "02001", "catastro", 2, "addresses", ""],  # no INE: the Catastro
            ["15680", "es:municipio:15902", "15902", "catastro", 42, "addresses", ""],  # two old DGC codes
            ["31001", "es:municipio:31201", "31201", "idena", 50, "addresses", "ine"]])
        self.assertIn(["02002", "es:municipio:02003", "02003", "catastro", 2, "addresses"], observations)
        self.assertEqual(observations[:3], [["01001", "es:municipio:01059", "01059", "eustat", 10, "portals"],
                                            ["02001", "es:municipio:02003", "02003", "ine", 40, "street_sections"],
                                            ["02001", "es:municipio:02003", "02003", "catastro", 500, "addresses"]])
        self.assertEqual(len(observations), 13)
        sections = report.sections
        self.assertEqual(sections["Códigos postales: código no válido (no se publica)"],
                         ["catastro: «53001» en Abengibre (es:municipio:02001), 9 direcciones"])
        self.assertEqual(sections["Códigos postales: código de relleno XX000 (no se publica)"],
                         ["ine: 02000 en Albacete (es:municipio:02003), 1 tramo",
                          "catastro: 02000 en Albacete (es:municipio:02003), 6 direcciones"])
        self.assertEqual(sections["Códigos postales: municipio sin cruce en catastro (no se publica)"],
                         ["02999: 3 direcciones"])
        self.assertEqual(sections["Códigos postales: municipio fuera del ámbito de la fuente (no se publica)"],
                         ["eustat: Pamplona/Iruña (es:municipio:31201), 1 portal"])
        self.assertEqual(sections["Códigos postales: municipio sin datos en su fuente (decide la siguiente)"],
                         ["Abengibre (es:municipio:02001): decide catastro; sin datos en ine",
                          "Oza-Cesuras (es:municipio:15902): decide catastro; sin datos en ine"])
        self.assertEqual(sections["Códigos postales: pares de dos o más fuentes que no se publican"],
                         ["31009 Pamplona/Iruña (es:municipio:31201): ine 2 tramos; catastro 4 direcciones"])
        self.assertEqual(sections["Códigos postales: pares publicados que no tiene ninguna otra fuente"], [
            "01001 Vitoria-Gasteiz (es:municipio:01059): eustat, 10 portales",
            "02001 Pamplona/Iruña (es:municipio:31201): idena, 3 direcciones",
            "02250 Abengibre (es:municipio:02001): catastro, 2 direcciones",
            "15680 Oza-Cesuras (es:municipio:15902): catastro, 42 direcciones"])
        self.assertEqual(sections["Códigos postales: código de otra provincia"],
                         ["02001 Pamplona/Iruña (es:municipio:31201): idena, 3 direcciones"])
        self.assertEqual(sections["Códigos postales: municipios sin código postal"], ["Sin direcciones (es:municipio:02002)"])
        self.assertEqual(report.summary["fuente catastro"], "579 direcciones; sin código postal: 4; 6 pares")
        self.assertEqual(report.summary["pares que tiene también otra fuente"], "3 (42,9%)")
        self.assertEqual(report.summary["municipios que decide catastro"], "2")

        previous = [r[:2] for r in rows[:5]] + [["01002", "es:municipio:01059"], ["03001", "es:municipio:03014"]]
        _, _, report = codigos_postales.build(counts, self._data(), previous)
        self.assertEqual(report.sections["Códigos postales: pares que desaparecen"],
                         ["01002 Vitoria-Gasteiz (es:municipio:01059)", "03001 es:municipio:03014"])
        self.assertEqual(report.sections["Códigos postales: pares nuevos"],
                         ["15680 Oza-Cesuras (es:municipio:15902)", "31001 Pamplona/Iruña (es:municipio:31201)"])
        self.assertIn("Códigos postales: aviso", report.sections)
        _, _, report = codigos_postales.build(counts, self._data(), [r[:2] for r in rows])
        self.assertNotIn("Códigos postales: aviso", report.sections)

    def test_ordered(self):
        item = lambda identity, count, unit: {"id": identity, "count": count, "unit": unit}
        same = [item("es:municipio:29067", 8, "portals"), item("es:municipio:29901", 900, "portals")]
        self.assertEqual([i["id"] for i in codigos_postales.ordered(same)], ["es:municipio:29901", "es:municipio:29067"])
        mixed = [item("es:municipio:28079", 2, "addresses"), item("es:municipio:28006", 90, "street_sections")]
        self.assertEqual(codigos_postales.ordered(mixed), mixed)  # as in the table

    def test_cases_check_and_orphans(self):
        import tempfile
        row = lambda code, ine, n, source="ine", also="": [code, f"es:municipio:{ine}", ine, source, n,
                                                           codigos_postales.SOURCES[source]["unit"], also]
        rows = [row(f"080{n:02d}", "08019", 10, "icgc", "ine") for n in range(1, 43)]
        rows += [row("29620", "29067", 5), row("29620", "29901", 90), row("31001", "31201", 9, "idena"),
                 row("01001", "01059", 9, "eustat", "ine catastro"), row("02250", "02001", 9),
                 row("28760", "28903", 367), row("28760", "28079", 33, "madrid", "ine")]
        self.assertEqual(codigos_postales.check_cases(rows), [])
        rows[42][4] = 100  # Málaga ahead of Torremolinos
        self.assertEqual(codigos_postales.check_cases(rows[1:-2] + rows[-1:] + rows[-2:-1]), [
            "es:municipio:08019 no tiene 08001",
            "29620 da ['es:municipio:29067'], se esperaba ['es:municipio:29901']",
            "28760 da ['es:municipio:28079', 'es:municipio:28903'], se esperaba ['es:municipio:28903', 'es:municipio:28079']"])
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / codigos_postales.FILE
            good = codigos_postales._canonical(rows)
            path.write_text(codigos_postales.table(good), encoding="utf-8")
            self.assertEqual(codigos_postales.check(path), [])
            self.assertEqual(codigos_postales.orphans(path, {"territories": [{"id": "es:municipio:08019"}]}),
                             ["es:municipio:01059: relanzar codigos-postales.yml",
                              "es:municipio:02001: relanzar codigos-postales.yml",
                              "es:municipio:28079: relanzar codigos-postales.yml",
                              "es:municipio:28903: relanzar codigos-postales.yml",
                              "es:municipio:29067: relanzar codigos-postales.yml",
                              "es:municipio:29901: relanzar codigos-postales.yml",
                              "es:municipio:31201: relanzar codigos-postales.yml"])
            path.write_text(codigos_postales.table(rows), encoding="utf-8")
            self.assertEqual(codigos_postales.check(path), [f"{codigos_postales.FILE} no está en forma canónica"])
            # A code of two units keeps its order (set by build); one of a single unit goes by count.
            swapped = good[:]
            i = next(n for n, r in enumerate(swapped) if r[0] == "28760")
            swapped[i], swapped[i + 1] = swapped[i + 1], swapped[i]
            path.write_text(codigos_postales.table(swapped), encoding="utf-8")
            self.assertEqual(codigos_postales.check(path), [])
            i = next(n for n, r in enumerate(swapped) if r[0] == "29620")
            swapped[i], swapped[i + 1] = swapped[i + 1], swapped[i]
            path.write_text(codigos_postales.table(swapped), encoding="utf-8")
            self.assertEqual(codigos_postales.check(path), [f"{codigos_postales.FILE} no está en forma canónica"])
            for bad in (["2800", "es:municipio:28079", "28079", "madrid", 5, "addresses", ""],
                        ["28000", "es:municipio:28079", "28079", "madrid", 5, "addresses", ""],
                        ["28001", "es:municipio:28079", "28078", "madrid", 5, "addresses", ""],
                        ["28001", "es:municipio:28079", "28079", "madrid", 0, "addresses", ""],
                        ["28001", "es:municipio:28079", "28079", "correos", 5, "addresses", ""],
                        ["28001", "es:municipio:28079", "28079", "madrid", 5, "portals", ""],
                        ["28001", "es:municipio:28079", "28079", "madrid", 5, "addresses", "madrid"],
                        ["28001", "es:municipio:28079", "28079", "madrid", 5, "addresses", "catastro ine"],
                        ["28001", "es:municipio:28079", "28079", "madrid", 5, "addresses"]):
                path.write_text(codigos_postales.table([bad]), encoding="utf-8")
                self.assertEqual(len(codigos_postales.check(path)), 1, bad)
            path.write_text("codigo,municipio\n", encoding="utf-8")
            self.assertEqual(len(codigos_postales.check(path)), 1)
            # The observations: one row per pair and source, in the order of the sources.
            path = Path(folder) / codigos_postales.OBSERVATIONS
            header = codigos_postales.OBSERVATION_HEADER
            obs = [["28001", "es:municipio:28079", "28079", "madrid", 5, "addresses"],
                   ["28001", "es:municipio:28079", "28079", "ine", 2, "street_sections"]]
            path.write_text(codigos_postales.table(obs, header), encoding="utf-8")
            self.assertEqual(codigos_postales.check(path, header), [])
            path.write_text(codigos_postales.table(obs[::-1], header), encoding="utf-8")
            self.assertEqual(codigos_postales.check(path, header), [f"{codigos_postales.OBSERVATIONS} no está en forma canónica"])
            path.write_text(codigos_postales.table(obs + obs[:1], header), encoding="utf-8")
            self.assertEqual(len(codigos_postales.check(path, header)), 1)

    def test_manifest_keeps_postal_entries(self):
        """generar.yml rewrites the manifest; the entries of the postal-code workflow stay."""
        import shutil
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            for name in ("territorios.json", "manifiesto.json", codigos_postales.FILE, codigos_postales.OBSERVATIONS):
                shutil.copy(ROOT / "pruebas" / "datos" / name, folder / name)
            data = json.loads((folder / "territorios.json").read_text(encoding="utf-8"))
            exportar.write(folder, data, [], {"otra": {"url": "u"}})
            manifest = json.loads((folder / "manifiesto.json").read_text(encoding="utf-8"))
            self.assertIn(codigos_postales.FILE, manifest["files"])
            self.assertIn(codigos_postales.OBSERVATIONS, manifest["files"])
            self.assertEqual(list(manifest["sources"]), ["otra"])  # the fixture source is not a postal one
            codigos_postales.write(folder, [["15001", "es:municipio:15030", "15030", "catastro", 9, "addresses", ""]],
                                   [["15001", "es:municipio:15030", "15030", "catastro", 9, "addresses"]],
                                   {"catastro_direcciones": {"url": "c"}})
            exportar.write(folder, data, [], {"otra": {"url": "u"}})
            manifest = json.loads((folder / "manifiesto.json").read_text(encoding="utf-8"))
            self.assertEqual(list(manifest["sources"]), ["otra", "catastro_direcciones"])
            self.assertEqual(exportar.check(folder), [])


class HandLists(unittest.TestCase):
    def test_every_community_has_names_in_every_interface_language(self):
        import csv
        with (ROOT / "fuentes" / "nombres-comunidades.csv").open(encoding="utf-8") as file:
            rows = list(csv.DictReader(file))
        pairs = {(r["ine"], r["lang"]) for r in rows if r["name"]}
        self.assertEqual(len(pairs), 19 * 6)


if __name__ == "__main__":
    unittest.main()
