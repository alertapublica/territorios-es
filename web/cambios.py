"""Changes between generations of datos/, read from the git history.

A generation is a commit of the current branch (first parent) that touches datos/: on main, the merge of each
data PR. Every CSV is compared row by row with the previous generation, with one key per file. Everything that
is published goes through git; the originals of each source do not, and only their footprint (SHA-256) and the
date they were read stay in datos/manifiesto.json, whose history says since when each footprint is the same.

compare() is pure and works on any two tables; history() reads git. The status page of the website draws the
result (web/estado.py); docs/estado.md does not carry it, because it has to come from files alone.
"""
from __future__ import annotations

import csv
import io
import json
import re
import subprocess
from pathlib import Path

DEFAULT_KEY = ("id",)
KEYS = {  # columns that identify a row, for the files where "id" alone does not
    "codigos.csv": ("id", "system"),
    "nombres.csv": ("id", "kind", "lang", "name"),
    "wikipedia.csv": ("id", "lang"),
    "codigos-postales.csv": ("postal_code", "id"),
    "codigos-postales-fuentes.csv": ("postal_code", "id", "source"),
}
DETAIL = 30  # a file with this many changes or fewer in a generation lists them one by one; with more, only the counts
PULL = re.compile(r"^Merge pull request #(\d+) from [^/\s]+/(\S+)|\(#(\d+)\)$")


def key_of(name: str) -> tuple[str, ...]:
    return KEYS.get(name, DEFAULT_KEY)


def compare(old: list[dict], new: list[dict], key: tuple[str, ...] = DEFAULT_KEY,
            columns: tuple[list[str], list[str]] | None = None) -> dict:
    """Rows added, removed and changed between two tables, and the columns that appear or disappear.

    A row is identified by the key columns present in both tables (by the whole row if none is). A new column
    is a change of structure, not a change in every row: only the columns that both tables have are compared.
    "changed" holds (key, column, before, after), one per cell. columns are the headers of both tables, for
    when one has no rows; without them, they are those of the first row, and an empty table has the header of
    the other one."""
    old_columns, new_columns = columns or ((list(old[0]) if old else []), (list(new[0]) if new else []))
    if not columns:
        old_columns, new_columns = old_columns or new_columns, new_columns or old_columns
    common = [c for c in new_columns if c in old_columns]
    by = tuple(c for c in key if c in common) or tuple(common)
    before = {tuple(row[c] for c in by): row for row in old}
    after = {tuple(row[c] for c in by): row for row in new}
    changed = [(k, c, before[k][c], row[c]) for k, row in after.items() if k in before
               for c in common if before[k][c] != row[c]]
    return {"added": [k for k in after if k not in before], "removed": [k for k in before if k not in after],
            "changed": changed,
            "columns_added": [c for c in new_columns if c not in old_columns],
            "columns_removed": [c for c in old_columns if c not in new_columns]}


def summary(old: list[dict] | None, new: list[dict] | None, key: tuple[str, ...] = DEFAULT_KEY,
            columns: tuple[list[str], list[str]] | None = None) -> dict | None:
    """What the status page shows of a file in one generation; None if nothing changed. old is None when the file
    is new and new is None when it is gone."""
    if old is None or new is None:
        rows = len(new if old is None else old)
        return {"new": old is None, "gone": new is None, "rows": rows, "added": rows if old is None else 0,
                "removed": rows if new is None else 0, "changed": 0, "fields": {}, "columns_added": [],
                "columns_removed": [], "detail": []}
    diff = compare(old, new, key, columns)
    if not any(diff.values()):
        return None
    fields = {}
    for _, column, _, _ in diff["changed"]:
        fields[column] = fields.get(column, 0) + 1
    detail = ([("+", k) for k in diff["added"]] + [("-", k) for k in diff["removed"]]
              + [("~", *change) for change in diff["changed"]])
    return {"new": False, "gone": False, "rows": len(new), "added": len(diff["added"]),
            "removed": len(diff["removed"]), "changed": len({k for k, _, _, _ in diff["changed"]}), "fields": fields,
            "columns_added": diff["columns_added"], "columns_removed": diff["columns_removed"],
            "detail": detail if len(detail) <= DETAIL else []}


def table(text: str) -> tuple[list[str], list[dict]]:
    """Header and rows of a CSV: the header apart, because a file may have no rows."""
    reader = csv.DictReader(io.StringIO(text, newline=""))
    return list(reader.fieldnames or []), list(reader)


def footprint(source: dict) -> str:
    """What identifies the content of a source in the manifest: its SHA-256, or those of its copies in fuentes/."""
    copies = source.get("copies") or {}
    return source.get("sha256") or " ".join(sorted(c.get("sha256", "") for c in copies.values()))


def _git(root: Path, *args: str) -> str | None:
    try:
        done = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, encoding="utf-8")
    except OSError:
        return None
    return done.stdout if done.returncode == 0 else None


def history(root: Path, folder: str = "datos") -> dict | None:
    """Every generation of `folder` in the git history of `root`, newest first, and since when each source has the
    footprint it has now. None without git, in a shallow clone or with no generation.

    {"generations": [{"commit", "date", "subject", "pull", "branch", "files": {name: summary()}, "touched": [name]}],
     (touched: every file of the folder whose content is not that of the previous generation, CSV or not)
     "sources": {key: {"retrieved", "since", "changes"}}}"""
    if (_git(root, "rev-parse", "--is-shallow-repository") or "").strip() != "false":
        return None
    log = _git(root, "log", "--first-parent", "--reverse", "--format=%H%x09%cs%x09%s", "--", folder)
    if not log:
        return None
    generations, blobs, tables, sources = [], {}, {}, {}
    for line in log.splitlines():
        commit, date, subject = line.split("\t", 2)
        listing = _git(root, "ls-tree", commit, folder + "/") or ""
        now = {Path(path).name: meta.split()[2] for meta, path in (x.split("\t", 1) for x in listing.splitlines())}
        files = {}
        for name in sorted(set(now) | set(blobs)):
            if not name.endswith(".csv") or now.get(name) == blobs.get(name):
                continue
            old = tables.pop(name, None)
            new = table(_git(root, "cat-file", "blob", now[name]) or "") if name in now else None
            if new is not None:
                tables[name] = new
            change = summary(old and old[1], new and new[1], key_of(name), (old[0], new[0]) if old and new else None)
            if change:
                files[name] = change
        manifest = now.get("manifiesto.json")
        if manifest and manifest != blobs.get("manifiesto.json"):
            current = json.loads(_git(root, "cat-file", "blob", manifest) or "{}").get("sources", {})
            for key, source in current.items():
                seen, mark = sources.get(key), footprint(source)
                if not seen:
                    sources[key] = {"footprint": mark, "since": source.get("retrieved") or date, "changes": 0}
                elif seen["footprint"] != mark:
                    seen.update(footprint=mark, since=source.get("retrieved") or date, changes=seen["changes"] + 1)
                sources[key]["retrieved"] = source.get("retrieved", "")
            sources = {key: seen for key, seen in sources.items() if key in current}
        touched = sorted(name for name in set(now) | set(blobs) if now.get(name) != blobs.get(name))
        blobs = now
        pull = PULL.search(subject)
        generations.append({"commit": commit, "date": date, "subject": subject,
                            "pull": int(pull.group(1) or pull.group(3)) if pull else None,
                            "branch": pull.group(2) if pull and pull.group(2) else "", "files": files,
                            "touched": touched})
    return {"generations": generations[::-1],
            "sources": {key: {k: v for k, v in seen.items() if k != "footprint"} for key, seen in sources.items()}}
