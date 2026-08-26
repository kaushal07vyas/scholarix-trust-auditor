"""
Affiliation integrity check.

Compares the stated `affiliation` field against the ORCID `current_institution` list.

Outputs one row per author with a status:
    MATCH               — stated affiliation is present in ORCID's list (fuzzy)
    CONFLICT            — stated affiliation is not in ORCID's list
    ORCID_NO_INST       — ORCID verified but no institution list
    ORCID_UNVERIFIED    — orcid.verified is False (untrusted source)
    NO_ORCID            — no ORCID id present at all
    NO_AFFILIATION      — profile has no stated affiliation

Usage:
    python -m src.checks.affiliation data/authors --out reports/affiliation.csv
"""
from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

from difflib import SequenceMatcher

from ..load_authors import Author, load_all


# common institution name variants that should collapse
STOPWORDS = {"the", "of", "at", "and", "&"}


def normalize(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"[^\w\s-]", " ", s)
    tokens = [t for t in s.split() if t and t not in STOPWORDS]
    return " ".join(tokens)


def token_set_ratio(a: str, b: str) -> int:
    """Cheap token-set ratio: intersect the token sets, then compare
    the intersection to each side. Returns 0-100."""
    ta, tb = set(a.split()), set(b.split())
    if not ta or not tb:
        return 0
    inter = " ".join(sorted(ta & tb))
    a_sorted = " ".join(sorted(ta))
    b_sorted = " ".join(sorted(tb))
    if not inter:
        return int(100 * SequenceMatcher(None, a_sorted, b_sorted).ratio())
    r1 = SequenceMatcher(None, inter, a_sorted).ratio()
    r2 = SequenceMatcher(None, inter, b_sorted).ratio()
    r3 = SequenceMatcher(None, a_sorted, b_sorted).ratio()
    return int(100 * max(r1, r2, r3))


def best_match_score(stated: str, candidates: list[str]) -> tuple[str | None, int]:
    """Return the best-matching candidate and its score (0-100)."""
    if not candidates:
        return None, 0
    stated_n = normalize(stated)
    best_c, best_s = None, 0
    for c in candidates:
        score = token_set_ratio(stated_n, normalize(c))
        if score > best_s:
            best_s, best_c = score, c
    return best_c, best_s


# threshold above which we call it a match. Tune based on results.
MATCH_THRESHOLD = 85


def check_author(a: Author) -> dict:
    row = {
        "author": a.name,
        "folder": a.folder,
        "stated_affiliation": a.affiliation or "",
        "orcid_id": a.orcid_id or "",
        "orcid_verified": a.orcid_verified,
        "orcid_institutions": " | ".join(a.orcid_institutions),
        "best_match": "",
        "match_score": 0,
        "status": "",
        "reason": "",
    }
    if not a.affiliation:
        row["status"] = "NO_AFFILIATION"
        row["reason"] = "Profile has no stated affiliation"
        return row
    if not a.orcid_id:
        row["status"] = "NO_ORCID"
        row["reason"] = "No ORCID id in profile — cannot cross-check"
        return row
    if not a.orcid_verified:
        row["status"] = "ORCID_UNVERIFIED"
        row["reason"] = "ORCID present but flagged unverified — treat as unknown"
        return row
    if not a.orcid_institutions:
        row["status"] = "ORCID_NO_INST"
        row["reason"] = "ORCID verified but returned no institution list"
        return row

    match, score = best_match_score(a.affiliation, a.orcid_institutions)
    row["best_match"] = match or ""
    row["match_score"] = score
    if score >= MATCH_THRESHOLD:
        row["status"] = "MATCH"
        row["reason"] = f"Stated affiliation matches ORCID entry '{match}' (score {score})"
    else:
        row["status"] = "CONFLICT"
        row["reason"] = (
            f"Stated affiliation not found in ORCID list "
            f"(closest: '{match}' at score {score})"
        )
    return row


def main():
    p = argparse.ArgumentParser()
    p.add_argument("root", help="Path to authors directory")
    p.add_argument("--out", default="reports/affiliation.csv")
    args = p.parse_args()

    authors = load_all(Path(args.root))
    rows = [check_author(a) for a in authors]

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    # print summary
    from collections import Counter
    counts = Counter(r["status"] for r in rows)
    print(f"\nAffiliation check ({len(rows)} authors) -> {out}")
    for status, n in counts.most_common():
        pct = 100 * n / len(rows)
        print(f"  {status:20s} {n:3d}  ({pct:.0f}%)")


if __name__ == "__main__":
    main()
