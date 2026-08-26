"""
Verification status check.

Right now the data lumps 'never checked' together with 'checked and failed' â€”
both look like `verified: False`. This teases them apart into:

    VERIFIED           â€” verified: True
    RATE_LIMITED       â€” verified: False and reason contains 429
    FETCH_ERROR        â€” verified: False with any other reason
    NEVER_CHECKED      â€” the field is null or the block is missing entirely
    NO_URL             â€” no personal_website / linkedin / etc. URL provided

Usage:
    python -m src.checks.verification data/authors --out reports/verification.csv
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path
from collections import Counter

from ..load_authors import Author, load_all

FIELDS = ["personal_website", "linkedin", "researchgate", "google_scholar"]


def classify(entry) -> tuple[str, str]:
    """Return (status, detail) for a single verification entry."""
    if entry is None:
        return "NEVER_CHECKED", "field is null"
    if isinstance(entry, str):
        # some fields might just store a URL as string
        return "URL_ONLY", entry
    if isinstance(entry, dict):
        if entry.get("verified") is True:
            return "VERIFIED", entry.get("url", "") or ""
        reason = (entry.get("reason") or "").strip()
        if not reason:
            return "NEVER_CHECKED", "no reason field"
        if "429" in reason:
            return "RATE_LIMITED", reason
        return "FETCH_ERROR", reason
    return "UNKNOWN", str(entry)[:100]


def check_author(a: Author) -> list[dict]:
    rows = []
    v = a.verification_block or {}
    for field in FIELDS:
        entry = v.get(field, None) if field in v else None
        # detect truly missing keys separately from null
        if field not in v:
            status, detail = "NEVER_CHECKED", "field absent from profile"
        else:
            status, detail = classify(v.get(field))
        rows.append({
            "author": a.name,
            "field": field,
            "status": status,
            "detail": detail,
        })
    return rows


def main():
    p = argparse.ArgumentParser()
    p.add_argument("root")
    p.add_argument("--out", default="reports/verification.csv")
    args = p.parse_args()

    authors = load_all(Path(args.root))
    all_rows = []
    for a in authors:
        all_rows.extend(check_author(a))

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(all_rows[0].keys()))
        w.writeheader()
        w.writerows(all_rows)

    # per-field breakdown
    print(f"\nVerification check ({len(authors)} authors x {len(FIELDS)} fields) -> {out}\n")
    for field in FIELDS:
        counts = Counter(r["status"] for r in all_rows if r["field"] == field)
        print(f"{field}:")
        for status, n in counts.most_common():
            print(f"  {status:15s} {n:3d}")
        print()


if __name__ == "__main__":
    main()

