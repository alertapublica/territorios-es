"""Optional Catastro services, with a fake fetch: invented answers of the same shape as the real
ones (seen on 2026-11-09). No network."""
import json
import unittest

from pruebas import ROOT
from territorios_es import Catalog
from territorios_es.catastro_online import CatastroError, locate_point, locate_reference

CATALOG = Catalog(json.loads((ROOT / "pruebas" / "datos" / "territorios.json").read_text(encoding="utf-8")))
NS = 'xmlns="http://www.catastro.meh.es/"'


def dnp(*places):
    """Consulta_DNPRC answer with one property per (province, municipality)."""
    items = "".join(f"<rcdnp><dt><loine><cp>{p}</cp><cm>{m}</cm></loine></dt></rcdnp>" for p, m in places)
    return f"<consulta_dnp {NS}><control><cudnp>{len(places)}</cudnp></control><lrcdnp>{items}</lrcdnp></consulta_dnp>"


def error(answer, message):
    return f"<{answer} {NS}><control><cuerr>1</cuerr></control><lerr><err><cod>1</cod><des>{message}</des></err></lerr></{answer}>"


def coordinates(pc1, pc2):
    return (f"<consulta_coordenadas {NS}><control><cucoor>1</cucoor><cuerr>0</cuerr></control><coordenadas><coord>"
            f"<pc><pc1>{pc1}</pc1><pc2>{pc2}</pc2></pc></coord></coordenadas></consulta_coordenadas>")


class Fake:
    def __init__(self, *answers):
        self.answers, self.urls = list(answers), []

    def __call__(self, url):
        self.urls.append(url)
        return self.answers.pop(0).encode()


class LocateReference(unittest.TestCase):
    def test_urban_reference(self):
        fetch = Fake(dnp(("15", "30")))
        found = locate_reference("1234567ab1234c", catalog=CATALOG, fetch=fetch)
        self.assertEqual((found["status"], found["territory"], found["reason"]), ("resolved", "es:municipio:15030", "catastro"))
        self.assertTrue(fetch.urls[0].endswith("/OVCCallejero.asmx/Consulta_DNPRC?Provincia=&Municipio=&RC=1234567AB1234C"))
        self.assertEqual(found["evidence"][0]["source"], "catastro:Consulta_DNPRC")

    def test_rustic_reference_agrees_or_conflicts(self):
        found = locate_reference("15900A00100192", catalog=CATALOG, fetch=Fake(dnp(("15", "30"), ("15", "30"))))
        self.assertEqual((found["status"], found["territory"]), ("resolved", "es:municipio:15030"))
        found = locate_reference("15900A00100192", catalog=CATALOG, fetch=Fake(dnp(("36", "38"))))
        self.assertEqual(found["status"], "conflict")

    def test_not_found_and_disagreement(self):
        found = locate_reference("1234567AB1234C", catalog=CATALOG, fetch=Fake(error("consulta_dnp", "NO EXISTE")))
        self.assertEqual((found["status"], found["reason"]), ("pending", "not_found"))
        self.assertEqual(found["evidence"][0]["reason"], "NO EXISTE")
        found = locate_reference("1234567AB1234C", catalog=CATALOG, fetch=Fake(dnp(("15", "30"), ("36", "38"))))
        self.assertEqual(found["status"], "conflict")
        found = locate_reference("1234567AB1234C", catalog=CATALOG, fetch=Fake(dnp(("15", "26"))))
        self.assertEqual((found["status"], found["reason"]), ("pending", "not_found"))  # merged municipality

    def test_no_request_for_what_is_not_a_reference(self):
        fetch = Fake()
        self.assertEqual(locate_reference("hola", catalog=CATALOG, fetch=fetch)["reason"], "not_a_reference")
        self.assertEqual(locate_reference("13096A001001920000YX", catalog=CATALOG, fetch=fetch)["reason"],
                         "invalid_check")
        self.assertEqual(fetch.urls, [])

    def test_unreadable_answer(self):
        self.assertRaises(CatastroError, locate_reference, "1234567AB1234C", catalog=CATALOG, fetch=Fake("<html>"))


class LocatePoint(unittest.TestCase):
    def test_point(self):
        fetch = Fake(coordinates("1234567", "AB1234C"), dnp(("15", "30")))
        found = locate_point(-8.4, 43.37, catalog=CATALOG, fetch=fetch)
        self.assertEqual((found["status"], found["territory"]), ("resolved", "es:municipio:15030"))
        self.assertIn("Consulta_RCCOOR?SRS=EPSG%3A4326&Coordenada_X=-8.4&Coordenada_Y=43.37", fetch.urls[0])
        self.assertEqual(found["evidence"][0], {"source": "catastro:Consulta_RCCOOR", "datum": "-8.4,43.37",
                                                "territory": None, "reason": "1234567AB1234C"})

    def test_no_parcel(self):
        fetch = Fake(error("consulta_coordenadas", "NO HAY PARCELA"))
        found = locate_point(-9.5, 43.0, catalog=CATALOG, fetch=fetch)
        self.assertEqual((found["status"], found["reason"]), ("pending", "not_found"))
        self.assertEqual(len(fetch.urls), 1)


if __name__ == "__main__":
    unittest.main()
