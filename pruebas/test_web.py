"""Open-data website: every language has every text, and the pages build from the fixture data."""
import json
import tempfile
import unittest
from pathlib import Path

from pruebas import ROOT

TEXTS = json.loads((ROOT / "web" / "textos.json").read_text(encoding="utf-8"))
UI_LANGS = ["es", "en", "ca", "gl", "eu", "oc"]


def keys(obj, prefix=""):
    found = set()
    for key, value in obj.items():
        found.add(prefix + key)
        if isinstance(value, dict):
            found |= keys(value, prefix + key + ".")
    return found


class Web(unittest.TestCase):
    def test_same_texts_in_every_language(self):
        for lang, texts in TEXTS.items():
            self.assertEqual(keys(texts), keys(TEXTS["es"]), lang)

    def test_every_interface_language_is_present(self):
        self.assertEqual(sorted(TEXTS), sorted(UI_LANGS))

    def test_every_csv_column_is_described(self):
        import web.construir as site
        for column in site._columns(ROOT / "pruebas" / "datos"):
            self.assertIn(column, TEXTS["es"]["columns"], column)

    def test_builds_from_fixture_data(self):
        import web.construir as site
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / "_site"
            site.build(out, ROOT / "pruebas" / "datos")
            for lang in TEXTS:
                html = (out / lang / "index.html").read_text(encoding="utf-8")
                self.assertIn(f'<html lang="{lang}">', html)
                self.assertIn("../datos/municipios.csv", html)
                self.assertIn('href="estado/"', html)
                status = (out / lang / "estado" / "index.html").read_text(encoding="utf-8")
                self.assertIn(f'<html lang="{lang}">', status)
                self.assertIn('class="mermaid"', status)
            self.assertTrue((out / "datos" / "territorios.json").exists())
            site.build(out, Path(folder) / "sin-datos")
            self.assertIn(TEXTS["es"]["no_data"].split(".")[0], (out / "es" / "index.html").read_text(encoding="utf-8"))


class Status(unittest.TestCase):
    def test_everything_in_the_repository_is_on_the_map(self):
        import web.estado as estado
        self.assertEqual(estado.problems(), [])

    def test_codes_keep_their_leading_zeros_in_the_database(self):
        import sqlite3
        import web.construir as site
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "datos.db"
            site.database(path, ROOT / "pruebas" / "datos")
            db = sqlite3.connect(path)
            try:
                ine = db.execute('SELECT ine FROM municipios WHERE id = "es:municipio:01059"').fetchone()[0]
                population = db.execute('SELECT typeof(population) FROM municipios LIMIT 1').fetchone()[0]
            finally:
                db.close()
        self.assertEqual(ine, "01059")
        self.assertEqual(population, "integer")

    def test_workflow_triggers_in_every_form(self):
        import web.estado as estado
        with tempfile.TemporaryDirectory() as folder:
            cases = {"on: [push, pull_request]\n": ["push", "pull_request"], "on: push\n": ["push"],
                     "on:\n  schedule:\n    - cron: '1 2 3 * *'\n  workflow_dispatch:\n": ["schedule", "workflow_dispatch"]}
            for text, triggers in cases.items():
                path = Path(folder) / "w.yml"
                path.write_text(text, encoding="utf-8")
                self.assertEqual(estado._workflow_triggers(path)[0], triggers, text)
            self.assertEqual(estado._workflow_triggers(path)[1], ["1 2 3 * *"])

    def test_tab_ids_have_no_accents(self):
        import web.estado as estado
        self.assertEqual(estado._anchor("Librería"), "libreria")
        self.assertEqual(estado._anchor("Fichièrs"), "fichiers")

    def test_markdown_builds_from_fixture_data(self):
        import web.estado as estado
        for lang in estado.OUT:
            text = estado.markdown(lang, ROOT / "pruebas" / "datos")
            self.assertIn("```mermaid", text)


if __name__ == "__main__":
    unittest.main()
