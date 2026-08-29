"""
ORCID public API client with local caching.

Docs: https://info.orcid.org/documentation/features/public-api/
No auth required for public endpoints.
"""
from __future__ import annotations

import json
from pathlib import Path

import httpx


CACHE_DIR = Path("cache/orcid")
BASE_URL = "https://pub.orcid.org/v3.0"
TIMEOUT = 15.0
USER_AGENT = "scholarix-trust-auditor/0.1 (research eval)"


def _cache_path(orcid_id: str) -> Path:
    return CACHE_DIR / f"{orcid_id}.json"


def _extract_institutions(payload: dict) -> list[str]:
    institutions = []
    activities = payload.get("activities-summary") or {}
    employments = activities.get("employments") or {}
    groups = employments.get("affiliation-group") or []
    for group in groups:
        summaries = group.get("summaries") or []
        for s in summaries:
            emp = s.get("employment-summary") or {}
            org = (emp.get("organization") or {}).get("name")
            if org:
                institutions.append(org)
    seen = set()
    out = []
    for i in institutions:
        if i not in seen:
            seen.add(i)
            out.append(i)
    return out


def fetch_record(orcid_id: str, force: bool = False) -> dict:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = _cache_path(orcid_id)

    if cache_file.exists() and not force:
        return json.loads(cache_file.read_text(encoding="utf-8"))

    url = f"{BASE_URL}/{orcid_id}/record"
    headers = {"Accept": "application/json", "User-Agent": USER_AGENT}

    try:
        r = httpx.get(url, headers=headers, timeout=TIMEOUT)
    except httpx.RequestError as e:
        result = {"status": "ERROR", "reason": f"network error: {e}"}
        cache_file.write_text(json.dumps(result), encoding="utf-8")
        return result

    if r.status_code == 404:
        result = {"status": "NOT_FOUND", "reason": f"ORCID {orcid_id} returned 404"}
    elif r.status_code == 429:
        return {"status": "RATE_LIMITED", "reason": "HTTP 429 from ORCID"}
    elif r.status_code >= 400:
        result = {"status": "ERROR", "reason": f"HTTP {r.status_code}"}
    else:
        try:
            payload = r.json()
            institutions = _extract_institutions(payload)
            result = {"status": "OK", "institutions": institutions, "raw": payload}
        except Exception as e:
            result = {"status": "ERROR", "reason": f"parse error: {e}"}

    cache_file.write_text(json.dumps(result), encoding="utf-8")
    return result


if __name__ == "__main__":
    import sys
    orcid_id = sys.argv[1] if len(sys.argv) > 1 else "0000-0001-8208-8568"
    result = fetch_record(orcid_id)
    print(f"Status: {result['status']}")
    if result["status"] == "OK":
        print(f"Institutions ({len(result['institutions'])}):")
        for i in result["institutions"]:
            print(f"  - {i}")
    else:
        print(f"Reason: {result.get('reason')}")
