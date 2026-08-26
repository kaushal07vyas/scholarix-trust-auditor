"""
Load all author folders into a queryable structure.
Usage:
    python -m src.load_authors data/authors
"""
from __future__ import annotations
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Author:
    folder: str
    name: str
    openalex_id: str | None
    affiliation: str | None
    metrics: dict[str, Any] = field(default_factory=dict)
    orcid_block: dict[str, Any] = field(default_factory=dict)
    verification_block: dict[str, Any] = field(default_factory=dict)
    counts_by_year: list[dict] = field(default_factory=list)
    publications: list[dict] = field(default_factory=list)
    broad_impact: list[dict] = field(default_factory=list)

    @property
    def orcid_id(self):
        return self.orcid_block.get("orcid_id")

    @property
    def orcid_verified(self):
        return bool(self.orcid_block.get("verified"))

    @property
    def orcid_institutions(self):
        val = self.orcid_block.get("current_institution") or []
        if isinstance(val, str):
            return [val]
        return list(val)


def load_author(folder: Path) -> Author:
    profile = json.loads((folder / "profile.json").read_text(encoding="utf-8"))
    pubs_path = folder / "publications.json"
    bi_path = folder / "broad_impact.json"

    publications = json.loads(pubs_path.read_text(encoding="utf-8")) if pubs_path.exists() else []
    broad_impact = json.loads(bi_path.read_text(encoding="utf-8")) if bi_path.exists() else []

    return Author(
        folder=folder.name,
        name=profile.get("name", folder.name),
        openalex_id=profile.get("id"),
        affiliation=profile.get("affiliation"),
        metrics=profile.get("metrics", {}) or {},
        orcid_block=profile.get("orcid", {}) or {},
        verification_block=profile.get("verification", {}) or {},
        counts_by_year=profile.get("counts_by_year", []) or [],
        publications=publications if isinstance(publications, list) else [],
        broad_impact=broad_impact if isinstance(broad_impact, list) else [],
    )


def load_all(root: Path):
    root = Path(root)
    authors = []
    for folder in sorted(root.iterdir()):
        if not folder.is_dir() or folder.name.startswith("."):
            continue
        if not (folder / "profile.json").exists():
            continue
        try:
            authors.append(load_author(folder))
        except Exception as e:
            print(f"[warn] failed to load {folder.name}: {e}", file=sys.stderr)
    return authors


def summarize(authors):
    print(f"Loaded {len(authors)} authors")
    print(f"  with ORCID id present:     {sum(1 for a in authors if a.orcid_id)}")
    print(f"  with ORCID verified=True:  {sum(1 for a in authors if a.orcid_verified)}")
    print(f"  with affiliation:          {sum(1 for a in authors if a.affiliation)}")
    print(f"  with >=1 publication:      {sum(1 for a in authors if a.publications)}")
    total_pubs = sum(len(a.publications) for a in authors)
    total_bi = sum(len(a.broad_impact) for a in authors)
    print(f"  total publications:        {total_pubs}")
    print(f"  total broad_impact rows:   {total_bi}")

    gs_reasons = {}
    for a in authors:
        gs = (a.verification_block or {}).get("google_scholar") or {}
        reason = gs.get("reason") if isinstance(gs, dict) else None
        key = reason if reason else ("verified" if gs.get("verified") else "missing")
        gs_reasons[key] = gs_reasons.get(key, 0) + 1
    print("\nGoogle Scholar verification status breakdown:")
    for k, v in sorted(gs_reasons.items(), key=lambda x: -x[1]):
        print(f"  {k or '(empty)'}: {v}")


if __name__ == "__main__":
    root = Path(sys.argv[1] if len(sys.argv) > 1 else "data/authors")
    authors = load_all(root)
    summarize(authors)
