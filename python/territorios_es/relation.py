"""Relations between a reference (a name, a code, a point) and a territory, with a status and
evidence. Generic part of Voceiro's «relacionador». js/relation.js mirrors this file.

status: «resolved» (one territory), «pending» (none or several candidates) or «conflict»
(evidence that contradicts itself). A pending or conflicting relation never picks a territory.
"""
from __future__ import annotations

STATUSES = ("resolved", "pending", "conflict")


def relation(status: str, territory: str | None = None, candidates=(), reason: str = "",
             evidence=()) -> dict:
    if status not in STATUSES:
        raise ValueError(f"Unknown status {status!r}")
    if (status == "resolved") != (territory is not None):
        raise ValueError("Only a resolved relation has a territory")
    return {"status": status, "territory": territory, "candidates": sorted(set(candidates)),
            "reason": reason, "evidence": list(evidence)}


def relate_name(catalog, text: str, within: str | None = None, levels=None) -> dict:
    """Resolved only when exactly one territory has that name in the given scope."""
    found = catalog.search(text, within=within, levels=levels)
    ids = sorted({c["id"] for c in found})
    evidence = [{"source": "name", "datum": text, "territory": c["id"], "reason": c["reason"]}
                for c in found]
    if len(ids) == 1:
        return relation("resolved", ids[0], ids, "name", evidence)
    return relation("pending", None, ids, "ambiguous" if ids else "not_found", evidence)


def combine(*relations: dict) -> dict:
    """Joins relations about the same reference. Resolved relations must agree; candidate lists
    narrow each other down; anything contradictory is a conflict."""
    evidence = [e for r in relations for e in r["evidence"]]
    if any(r["status"] == "conflict" for r in relations):
        ids = {c for r in relations for c in r["candidates"]}
        return relation("conflict", None, ids, "conflict", evidence)
    possible = None
    for r in relations:
        options = {r["territory"]} if r["status"] == "resolved" else set(r["candidates"])
        if r["status"] == "pending" and not options:
            continue  # nothing found: no information
        possible = options if possible is None else possible & options
        if not possible:
            ids = {c for r in relations for c in ([r["territory"]] if r["territory"] else r["candidates"])}
            return relation("conflict", None, ids, "contradiction", evidence)
    if possible is None:
        return relation("pending", None, (), "not_found", evidence)
    if len(possible) == 1:
        (only,) = possible
        return relation("resolved", only, possible, "combined", evidence)
    return relation("pending", None, possible, "ambiguous", evidence)
