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

    def test_contrast_between_sources_from_fixture_data(self):
        import web.estado as estado
        text = estado.markdown("es", ROOT / "pruebas" / "datos")
        t = TEXTS["es"]["estado"]
        for title in ("s_contrast", "contrast_cp_support", "contrast_cp_sources", "contrast_names", "contrast_codes"):
            self.assertIn(t[title], text, title)
        self.assertNotIn(f"## {t['s_changes']}", text)  # the changes come from git: only on the website


class Changes(unittest.TestCase):
    OLD = [{"id": "a", "name": "A", "n": "1"}, {"id": "b", "name": "B", "n": "2"}, {"id": "c", "name": "C", "n": "3"}]

    def test_rows_added_removed_and_changed(self):
        from web import cambios
        new = [{"id": "a", "name": "A", "n": "1"}, {"id": "b", "name": "Be", "n": "20"}, {"id": "d", "name": "D", "n": "4"}]
        diff = cambios.compare(self.OLD, new)
        self.assertEqual(diff["added"], [("d",)])
        self.assertEqual(diff["removed"], [("c",)])
        self.assertEqual(diff["changed"], [(("b",), "name", "B", "Be"), (("b",), "n", "2", "20")])
        self.assertEqual((diff["columns_added"], diff["columns_removed"]), ([], []))
        self.assertFalse(any(cambios.compare(self.OLD, list(reversed(self.OLD))).values()))  # the order is not a change

    def test_a_new_column_is_not_a_change_in_every_row(self):
        from web import cambios
        new = [{"id": r["id"], "name": r["name"], "extra": "x"} for r in self.OLD]
        diff = cambios.compare(self.OLD, new)
        self.assertEqual((diff["columns_added"], diff["columns_removed"]), (["extra"], ["n"]))
        self.assertEqual((diff["added"], diff["removed"], diff["changed"]), ([], [], []))

    def test_compound_key(self):
        from web import cambios
        old = [{"postal_code": "15001", "id": "x", "count": "1"}, {"postal_code": "15001", "id": "y", "count": "2"}]
        new = [{"postal_code": "15001", "id": "x", "count": "5"}, {"postal_code": "15002", "id": "y", "count": "2"}]
        diff = cambios.compare(old, new, cambios.key_of("codigos-postales.csv"))
        self.assertEqual(diff["added"], [("15002", "y")])
        self.assertEqual(diff["removed"], [("15001", "y")])
        self.assertEqual(diff["changed"], [(("15001", "x"), "count", "1", "5")])

    def test_summary_lists_few_changes_and_counts_many(self):
        from web import cambios
        self.assertIsNone(cambios.summary(self.OLD, self.OLD))
        new = cambios.summary(None, self.OLD)
        self.assertEqual((new["new"], new["added"], new["detail"]), (True, 3, []))
        many = [{"id": str(i), "n": "0"} for i in range(cambios.DETAIL + 1)]
        few = cambios.summary(many, [{**r, "n": "1"} for r in many[:cambios.DETAIL]] + many[cambios.DETAIL:])
        self.assertEqual((few["changed"], len(few["detail"])), (cambios.DETAIL, cambios.DETAIL))
        change = cambios.summary(many, [{**r, "n": "1"} for r in many])
        self.assertEqual((change["changed"], change["fields"], change["detail"]),
                         (cambios.DETAIL + 1, {"n": cambios.DETAIL + 1}, []))

    def test_history_from_git_and_changes_tab(self):
        import subprocess
        import web.construir as site
        from web import cambios
        with tempfile.TemporaryDirectory() as folder:
            repo = Path(folder) / "repo"
            (repo / "datos").mkdir(parents=True)
            self.assertIsNone(cambios.history(repo))  # not a git repository

            def git(*args):
                subprocess.run(["git", "-C", str(repo), "-c", "user.name=prueba", "-c", "user.email=prueba@example.org",
                                "-c", "commit.gpgsign=false", *args], check=True, capture_output=True)

            def generation(subject, municipios, sha):
                (repo / "datos" / "municipios.csv").write_text(municipios, encoding="utf-8")
                (repo / "datos" / "manifiesto.json").write_text(json.dumps({"sources": {
                    "ine_municipios": {"sha256": sha, "retrieved": subject[-10:]}}}), encoding="utf-8")
                git("add", "datos")
                git("commit", "-q", "-m", subject)

            git("init", "-q")
            generation("datos: 2026-01-03", "id,official\nes:municipio:01001,Uno\nes:municipio:01002,Dos\n", "aa")
            (repo / "otro.txt").write_text("no toca datos/", encoding="utf-8")
            git("add", "otro.txt")
            git("commit", "-q", "-m", "otra cosa")
            generation("datos: 2026-02-03", "id,official\nes:municipio:01001,Uno\nes:municipio:01002,Dos\n", "aa")
            generation("Nombre nuevo (#7) 2026-03-03", "id,official\nes:municipio:01001,Un\nes:municipio:01003,Tres\n", "bb")
            self.assertEqual(cambios.PULL.search("Merge pull request #54 from alertapublica/entidades-menores").group(1, 2),
                             ("54", "entidades-menores"))
            self.assertEqual(cambios.PULL.search("Datos nuevos (#60)").group(3), "60")
            history = cambios.history(repo)
            newest, middle, oldest = history["generations"]
            self.assertTrue(oldest["files"]["municipios.csv"]["new"])
            self.assertEqual(middle["files"], {})  # only the manifest
            change = newest["files"]["municipios.csv"]
            self.assertEqual((change["added"], change["removed"], change["changed"]), (1, 1, 1))
            self.assertIn(("~", ("es:municipio:01001",), "official", "Uno", "Un"), change["detail"])
            self.assertEqual(history["sources"]["ine_municipios"],
                             {"since": "2026-03-03", "changes": 1, "retrieved": "2026-03-03"})

            out = Path(folder) / "_site"
            t = TEXTS["es"]["estado"]
            site.build(out, ROOT / "pruebas" / "datos", history)
            status = (out / "es" / "estado" / "index.html").read_text(encoding="utf-8")
            self.assertIn(f'<a href="#{t["s_changes"].lower()}">', status)
            self.assertIn("«Uno» → «Un»", status)
            self.assertIn(t["only_manifest"], status)
            site.build(out, ROOT / "pruebas" / "datos")
            status = (out / "es" / "estado" / "index.html").read_text(encoding="utf-8")
            self.assertNotIn(f'<a href="#{t["s_changes"].lower()}">', status)
            self.assertIn(f'<a href="#{t["s_contrast"].lower()}">', status)


if __name__ == "__main__":
    unittest.main()
