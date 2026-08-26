"""
Publication count sanity check.

Compares the metrics.publications count (what the profile claims) against:
  - actual length of publications.json
  - sum of counts_by_year works_count

A large gap suggests either an inflated metric or an incomplete publication list.
Either way it's a trust signal worth flagging.

Usage:
    python -m src.checks.pub_count data/authors --out reports/pub_count.csv
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path
from collections import Counter

from ..load_authors import Author, load_all


def check_author(a: Author) -> dict:
    stated = a.metrics.get("publications")
    actual = len(a.publications)
    sum_by_year = sum(y.get("works_count", 0) for y in a.counts_by_year)

    if stated is None:
        status = "NO_STATED_COUNT"
        gap = None
    else:
        # gap between what the profile claims and what's in the file
        gap = stated - actual
        rel = abs(gap) / stated if stated else 0
        if rel <= 0.05:
            status = "MATCH"
        elif rel <= 0.25:
            status = "MINOR_GAP"
        else:
            status = "LARGE_GAP"

    return {
        "author": a.name,
        "stated_publications": stated if stated is not None else "",
        "actual_in_file": actual,
        "sum_counts_by_year": sum_by_year,
        "gap_stated_minus_actual": gap if gap is not None else "",
        "status": status,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("root")
    p.add_argument("--out", default="reports/pub_count.csv")
    args = p.parse_args()

    authors = load_all(Path(args.root))
    rows = [check_author(a) for a in authors]

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    counts = Counter(r["status"] for r in rows)
    print(f"\nPublication count check ({len(rows)} authors) -> {out}")
    for status, n in counts.most_common():
        print(f"  {status:20s} {n:3d}")

    # show worst offenders
    print("\nLargest gaps (stated - actual):")
    interesting = sorted(
        [r for r in rows if isinstance(r["gap_stated_minus_actual"], int)],
        key=lambda r: -abs(r["gap_stated_minus_actual"]),
    )[:10]
    for r in interesting:
        print(f"  {r['author']:40s} stated={r['stated_publications']:>5}  "
              f"actual={r['actual_in_file']:>4}  gap={r['gap_stated_minus_actual']:>+5}")


if __name__ == "__main__":
    main()

