"""
Live affiliation check.

Compares the stated `affiliation` field against the ORCID API's real
employment history (not the potentially-stale ORCID block in profile.json).

Also flags when the file's ORCID block disagrees with live ORCID.

Usage:
    python -m src.checks.affiliation_live data/authors --out reports/affiliation_live.csv
"""
from __future__ import annotations

import argparse
import csv
import re
from difflib import SequenceMatcher
from pathlib import Path
from collections import Counter

from ..load_authors import Author, load_all
from ..clients.orcid import fetch_record


STOPWORDS = {"the", "of", "at", "and", "&"}
MATCH_THRESHOLD = 85


def normalize(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"[^\w\s-]", " ", s)
    tokens = [t for t in s.split() if t and t not in STOPWORDS]
    return " ".join(tokens)


def token_set_ratio(a: str, b: str) -> int:
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


def best_match(stated: str, candidates: list[str]) -> tuple[str | None, int]:
    if not candidates:
        return None, 0
    stated_n = normalize(stated)
    best_c, best_s = None, 0
    for c in candidates:
        s = token_set_ratio(stated_n, normalize(c))
        if s > best_s:
            best_s, best_c = s, c
    return best_c, best_s


def check_author(a: Author) -> dict:
    row = {
        "author": a.name,
        "stated_affiliation": a.affiliation or "",
        "orcid_id": a.orcid_id or "",
        "file_orcid_institutions": " | ".join(a.orcid_institutions),
        "live_orcid_institutions": "",
        "file_vs_live_agree": "",
        "live_match_score": 0,
        "live_best_match": "",
        "status": "",
        "reason": "",
    }

    if not a.affiliation:
        row["status"] = "NO_AFFILIATION"
        row["reason"] = "Profile has no affiliation"
        return row
    if not a.orcid_id:
        row["status"] = "NO_ORCID"
        row["reason"] = "No ORCID id in profile"
        return row

    # hit the ORCID API (uses cache)
    result = fetch_record(a.orcid_id)
    if result["status"] != "OK":
        row["status"] = f"ORCID_{result['status']}"
        row["reason"] = result.get("reason", "")
        return row

    live_inst = result["institutions"]
    row["live_orcid_institutions"] = " | ".join(live_inst)

    # do the file's ORCID block and live ORCID agree?
    file_set = set(a.orcid_institutions)
    live_set = set(live_inst)
    if file_set == live_set:
        row["file_vs_live_agree"] = "IDENTICAL"
    elif file_set & live_set:
        row["file_vs_live_agree"] = "PARTIAL"
    else:
        row["file_vs_live_agree"] = "DISAGREE"

    if not live_inst:
        row["status"] = "ORCID_NO_EMPLOYMENT"
        row["reason"] = "ORCID record exists but has no employment history"
        return row

    match, score = best_match(a.affiliation, live_inst)
    row["live_best_match"] = match or ""
    row["live_match_score"] = score

    if score >= MATCH_THRESHOLD:
        row["status"] = "MATCH"
        row["reason"] = f"Stated affiliation matches live ORCID entry '{match}' (score {score})"
    else:
        row["status"] = "CONFLICT"
        row["reason"] = (
            f"Stated affiliation not in live ORCID list "
            f"(closest: '{match}' at score {score})"
        )
    return row


def main():
    p = argparse.ArgumentParser()
    p.add_argument("root")
    p.add_argument("--out", default="reports/affiliation_live.csv")
    args = p.parse_args()

    authors = load_all(Path(args.root))
    rows = [check_author(a) for a in authors]

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    print(f"\nLive affiliation check ({len(rows)} authors) -> {out}\n")

    print("Overall status:")
    for status, n in Counter(r["status"] for r in rows).most_common():
        print(f"  {status:25s} {n:3d}")

    print("\nFile ORCID vs Live ORCID (for authors we could fetch):")
    checked = [r for r in rows if r["file_vs_live_agree"]]
    for status, n in Counter(r["file_vs_live_agree"] for r in checked).most_common():
        print(f"  {status:15s} {n:3d}")


if __name__ == "__main__":
    main()
