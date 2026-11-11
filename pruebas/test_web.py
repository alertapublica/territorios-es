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

    def test_markdown_builds_from_fixture_data(self):
        import web.estado as estado
        for lang in estado.OUT:
            text = estado.markdown(lang, ROOT / "pruebas" / "datos")
            self.assertIn("```mermaid", text)


if __name__ == "__main__":
    unittest.main()
