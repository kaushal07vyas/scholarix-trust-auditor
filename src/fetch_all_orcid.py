"""
Fetch ORCID records for every author that has an ORCID id.
Uses the cache in cache/orcid so re-runs are free.

Usage:
    python -m src.fetch_all_orcid data/authors
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

from .load_authors import load_all
from .clients.orcid import fetch_record


def main():
    root = Path(sys.argv[1] if len(sys.argv) > 1 else "data/authors")
    authors = load_all(root)

    to_fetch = [a for a in authors if a.orcid_id]
    print(f"Fetching ORCID records for {len(to_fetch)} authors...\n")

    stats = {"OK": 0, "NOT_FOUND": 0, "RATE_LIMITED": 0, "ERROR": 0}
    for i, a in enumerate(to_fetch, 1):
        result = fetch_record(a.orcid_id)
        status = result["status"]
        stats[status] = stats.get(status, 0) + 1

        if status == "OK":
            n = len(result["institutions"])
            print(f"  [{i:2d}/{len(to_fetch)}] {a.name:40s} {a.orcid_id}  OK  ({n} inst)")
        else:
            print(f"  [{i:2d}/{len(to_fetch)}] {a.name:40s} {a.orcid_id}  {status}  {result.get('reason','')}")

        if status != "OK" or i < len(to_fetch):
            time.sleep(0.1)

    print(f"\nSummary:")
    for k, v in stats.items():
        print(f"  {k:15s} {v}")


if __name__ == "__main__":
    main()
