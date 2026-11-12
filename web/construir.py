"""Builds the open-data website (GitHub Pages) from datos/ and web/textos.json.

    python web/construir.py --salida _site [--datos datos]

One page per language plus a language chooser; the data files are copied under datos/.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import sqlite3
from html import escape
from pathlib import Path

try:
    from . import estado
except ImportError:  # run as a script: python web/construir.py
    import estado

ROOT = Path(__file__).resolve().parents[1]
REPO = "https://github.com/alertapublica/territorios-es"
FILES = ["territorios.json", "paises.csv", "comunidades.csv", "provincias.csv", "islas.csv", "partidos-judiciales.csv",
         "zonas-aviso.csv", "comarcas.csv",
         "municipios.csv", "codigos.csv", "codigos-postales.csv", "codigos-postales-fuentes.csv", "entidades.csv",
         "nombres.csv",
         "wikipedia.csv", "manifiesto.json"]
GENERIC = {"name_": "name_xx", "short_": "short_xx"}

CSS = """:root{--bg:#fdfdfc;--fg:#1d1d1b;--muted:#5d5d58;--line:#dcdcd6;--accent:#0b5cad;--note:#fff6d6}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#151514;--fg:#ececea;--muted:#a9a9a3;
--line:#3a3a36;--accent:#7db4f0;--note:#3a3312}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);
font:16px/1.55 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
main,header,footer{max-width:60rem;margin:0 auto;padding:0 16px}header{padding-top:24px}
h1{font-size:1.9rem;margin:.2em 0 0}h2{margin-top:2em;border-bottom:1px solid var(--line);padding-bottom:.2em}
.sub{color:var(--muted);margin:.2em 0 1em}a{color:var(--accent)}nav ul{list-style:none;padding:0;margin:0;
display:flex;flex-wrap:wrap;gap:.4em 1em}nav a[aria-current]{font-weight:700;text-decoration:none;color:var(--fg)}
.note{background:var(--note);padding:.6em .9em;border-radius:6px}.table{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:.95rem}th,td{text-align:left;vertical-align:top;
padding:.45em .6em;border-bottom:1px solid var(--line)}td.n{text-align:right;white-space:nowrap}
code{font-size:.9em;overflow-wrap:anywhere}dt{font-family:ui-monospace,monospace;margin-top:.6em}dd{margin:0 0 0 1.2em}
footer{color:var(--muted);padding-bottom:32px;margin-top:3em}
.top{display:flex;flex-wrap:wrap;gap:.4em 1.2em;align-items:center;margin-bottom:.8em}.top .langs{margin-left:auto}"""


def _size(n: int) -> str:
    return f"{n / 1_048_576:.1f} MB" if n >= 1_048_576 else f"{max(1, round(n / 1024))} KB"


def _rows(path: Path) -> int | None:
    if path.suffix == ".csv":
        with path.open(encoding="utf-8") as f:
            return sum(1 for _ in f) - 1
    if path.name == "territorios.json":
        return len(json.loads(path.read_text(encoding="utf-8"))["territories"])
    return None


def _columns(datos: Path) -> list[str]:
    seen = []
    for name in FILES:
        path = datos / name
        if path.suffix != ".csv" or not path.exists():
            continue
        with path.open(encoding="utf-8") as f:
            header = f.readline().strip().split(",")
        for column in header:
            for prefix, generic in GENERIC.items():
                if column.startswith(prefix) and column != "name":
                    column = generic
            if column not in seen:
                seen.append(column)
    return seen


INTEGER = re.compile(r"-?(0|[1-9][0-9]*)")
REAL = re.compile(r"-?(0|[1-9][0-9]*)\.[0-9]+")


def database(path: Path, datos: Path):
    """Every published CSV in one SQLite file, to explore it in Datasette Lite. A column is a number only if all its
    values are written as numbers with no leading zero, so codes such as 01001 stay text."""
    path.unlink(missing_ok=True)
    db = sqlite3.connect(path)
    try:
        for name in FILES:
            source = datos / name
            if source.suffix != ".csv" or not source.exists():
                continue
            with source.open(encoding="utf-8", newline="") as f:
                rows = list(csv.reader(f))
            header, rows = rows[0], rows[1:]
            types = []
            for i in range(len(header)):
                values = [row[i] for row in rows if row[i] != ""]
                kind = ("INTEGER" if values and all(INTEGER.fullmatch(v) for v in values) else
                        "REAL" if values and all(INTEGER.fullmatch(v) or REAL.fullmatch(v) for v in values) else "TEXT")
                types.append(kind)
            table = source.stem
            db.execute(f'CREATE TABLE "{table}" (' + ", ".join(f'"{c}" {k}' for c, k in zip(header, types)) + ")")
            db.executemany(f'INSERT INTO "{table}" VALUES (' + ", ".join("?" * len(header)) + ")",
                           [[None if v == "" else v for v in row] for row in rows])
        db.commit()
    finally:
        db.close()


def top_nav(lang: str, t: dict, status: bool) -> str:
    """Data · Status · GitHub, the same on the data pages and on the status page."""
    link = f'<a href="estado/">{escape(t["nav_status"])}</a>' if status else ""
    return (f'<nav class="top"><strong>{escape(t["nav_data"])}</strong>{link}'
            f'<a href="{REPO}">GitHub</a></nav>')


def page(lang: str, texts: dict, all_texts: dict, datos: Path | None) -> str:
    t = texts[lang]
    nav = "".join(
        f'<li><a href="../{code}/" hreflang="{code}" lang="{code}"'
        f'{" aria-current=page" if code == lang else ""}>{escape(all_texts[code]["language_name"])}</a></li>'
        for code in all_texts)
    alternates = "".join(f'<link rel="alternate" hreflang="{c}" href="../{c}/">' for c in all_texts)
    parts = [f"<p>{escape(t['intro'])}</p>", f'<p class="note">{escape(t["in_progress"])}</p>']
    if t.get("review"):
        parts.append(f'<p class="note">{escape(t["review"])}</p>')
    manifest = json.loads((datos / "manifiesto.json").read_text(encoding="utf-8")) if datos else None
    if not manifest:
        parts.append(f'<p>{escape(t["no_data"])} <a href="{REPO}/blob/main/docs/">{escape(t["repository"])}</a></p>')
    else:
        rows = []
        for name in FILES:
            path = datos / name
            if not path.exists():
                continue
            count = _rows(path)
            rows.append(f'<tr><td><a href="../datos/{name}" download><code>{name}</code></a></td>'
                        f'<td>{escape(t["files"].get(name, ""))}</td>'
                        f'<td class="n">{"" if count is None else f"{count:,}".replace(",", ".")}</td>'
                        f'<td class="n">{_size(path.stat().st_size)}</td></tr>')
        parts.append(f'<h2>{escape(t["files_heading"])}</h2><div class="table"><table><thead><tr>'
                     f'<th>{escape(t["file"])}</th><th>{escape(t["description"])}</th>'
                     f'<th>{escape(t["rows"])}</th><th>{escape(t["size"])}</th></tr></thead>'
                     f'<tbody>{"".join(rows)}</tbody></table></div>')
        terms = "".join(f'<dt>{escape(c)}</dt><dd>{escape(t["columns"].get(c, ""))}</dd>' for c in _columns(datos))
        parts.append(f'<h2>{escape(t["columns_heading"])}</h2><dl>{terms}</dl>')
        sources = []
        for key, source in sorted(manifest.get("sources", {}).items()):
            url = source.get("url", "")
            link = f'<a href="{escape(url.split(" ")[0])}">{escape(key)}</a>' if url.startswith("http") else escape(key)
            sources.append(f'<tr><td>{link}</td><td>{escape(source.get("licence", ""))}</td>'
                           f'<td class="n">{escape(source.get("retrieved", ""))}</td></tr>')
        parts.append(f'<h2>{escape(t["sources_heading"])}</h2><div class="table"><table><thead><tr>'
                     f'<th>{escape(t["source"])}</th><th>{escape(t["licence"])}</th><th>{escape(t["retrieved"])}</th>'
                     f'</tr></thead><tbody>{"".join(sources)}</tbody></table></div>')
    parts.append(f'<h2>{escape(t["names_heading"])}</h2><p>{escape(t["names_text"])}</p>')
    parts.append(f'<h2>{escape(t["library_heading"])}</h2><p>{escape(t["library_text"])}</p>'
                 f'<pre><code>pip install "territorios-es @ git+{REPO}@vX.Y.Z"\n'
                 f'npm install github:alertapublica/territorios-es#vX.Y.Z</code></pre>')
    return (f'<!doctype html><html lang="{lang}"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{escape(t["title"])}</title><meta name="description" content="{escape(t["subtitle"])}">'
            f'{alternates}<link rel="stylesheet" href="../estilo.css"></head><body>'
            f'<header>{top_nav(lang, t, bool(datos))}<nav aria-label="{escape(t["languages"])}"><ul>{nav}</ul></nav>'
            f'<h1>{escape(t["title"])}</h1><p class="sub">{escape(t["subtitle"])}</p></header>'
            f'<main>{"".join(parts)}</main>'
            f'<footer><p><a href="{REPO}">{escape(t["repository"])}</a>. {escape(t["licence_code"])}</p></footer>'
            f'</body></html>\n')


def chooser(texts: dict) -> str:
    links = "".join(f'<li><a href="{c}/" hreflang="{c}" lang="{c}">{escape(t["language_name"])}</a></li>'
                    for c, t in texts.items())
    codes = json.dumps(list(texts))
    return ('<!doctype html><html lang="es"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{escape(texts["es"]["title"])}</title><link rel="stylesheet" href="estilo.css">'
            f'<script>(function(){{var c={codes};var l=(navigator.languages||[navigator.language||""]);'
            'for(var i=0;i<l.length;i++){var k=String(l[i]).toLowerCase().split("-")[0];'
            'if(c.indexOf(k)>=0){location.replace(k+"/");return;}}})();</script></head><body>'
            f'<header><h1>{escape(texts["es"]["title"])}</h1></header><main><nav aria-label="Idiomas / Languages">'
            f'<ul>{links}</ul></nav></main></body></html>\n')


def build(out: Path, datos: Path | None):
    texts = json.loads((ROOT / "web" / "textos.json").read_text(encoding="utf-8"))
    if datos and not (datos / "manifiesto.json").exists():
        datos = None
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    (out / "estilo.css").write_text(CSS, encoding="utf-8")
    (out / "index.html").write_text(chooser(texts), encoding="utf-8")
    for lang in texts:
        (out / lang).mkdir()
        (out / lang / "index.html").write_text(page(lang, texts, texts, datos), encoding="utf-8")
    if datos:
        (out / "datos").mkdir()
        for name in FILES:
            if (datos / name).exists():
                shutil.copy2(datos / name, out / "datos" / name)
        database(out / "datos" / estado.DATABASE, datos)
        for lang in texts:
            (out / lang / "estado").mkdir()
            (out / lang / "estado" / "index.html").write_text(estado.page(lang, datos), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--salida", type=Path, default=ROOT / "_site")
    parser.add_argument("--datos", type=Path, default=ROOT / "datos")
    args = parser.parse_args()
    build(args.salida, args.datos)


if __name__ == "__main__":
    main()
