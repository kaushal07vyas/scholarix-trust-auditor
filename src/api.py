"""
FastAPI backend for the Scholarix Trust Auditor.

Run:
    uvicorn src.api:app --reload

Then open http://127.0.0.1:8000
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from .load_authors import load_all, Author
from .checks.affiliation import check_author as check_affiliation
from .checks.verification import check_author as check_verification
from .checks.pub_count import check_author as check_pub_count
from .checks.affiliation_live import check_author as check_affiliation_live


DATA_ROOT = Path("data/authors")
templates = Jinja2Templates(directory="templates")

app = FastAPI(title="Scholarix Trust Auditor")

# load once at startup
AUTHORS: list[Author] = load_all(DATA_ROOT)
AUTHORS_BY_FOLDER = {a.folder: a for a in AUTHORS}


def audit(a: Author) -> dict:
    """Run all four checks and return a merged view."""
    affiliation = check_affiliation(a)
    affiliation_live = check_affiliation_live(a)
    verification_rows = check_verification(a)
    pub_count = check_pub_count(a)

    # simple overall trust label based on findings
    problems = []
    if affiliation["status"] == "CONFLICT":
        problems.append("stated affiliation conflicts with ORCID (file)")
    if affiliation_live["status"] == "CONFLICT":
        problems.append("stated affiliation conflicts with live ORCID")
    if affiliation_live["status"] == "ORCID_NO_EMPLOYMENT":
        problems.append("ORCID has no employment history but file claims institutions")
    if affiliation_live.get("file_vs_live_agree") == "DISAGREE":
        problems.append("file's ORCID data does not match live ORCID")
    elif affiliation_live.get("file_vs_live_agree") == "PARTIAL":
        problems.append("file's ORCID data partially disagrees with live ORCID")
    if pub_count["status"] == "LARGE_GAP":
        problems.append(f"publication list is incomplete ({pub_count['actual_in_file']} of {pub_count['stated_publications']} shown)")
    silent_failures = sum(
        1 for r in verification_rows
        if r["status"] in ("RATE_LIMITED", "FETCH_ERROR", "NEVER_CHECKED")
    )
    if silent_failures == len(verification_rows):
        problems.append("all verification channels failed silently or were never attempted")

    if not problems:
        trust = "OK"
    elif len(problems) >= 3:
        trust = "LOW"
    else:
        trust = "MEDIUM"

    return {
        "author": {
            "name": a.name,
            "folder": a.folder,
            "affiliation": a.affiliation,
            "orcid_id": a.orcid_id,
            "openalex_id": a.openalex_id,
            "metrics": a.metrics,
            "topics": a.topics if hasattr(a, "topics") else [],
        },
        "trust": trust,
        "problems": problems,
        "affiliation": affiliation,
        "affiliation_live": affiliation_live,
        "verification": verification_rows,
        "pub_count": pub_count,
    }


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    author_list = [
        {"folder": a.folder, "name": a.name, "affiliation": a.affiliation}
        for a in AUTHORS
    ]
    return templates.TemplateResponse(
        request, "index.html", {"authors": author_list}
    )


@app.get("/api/authors")
def api_authors():
    return [
        {"folder": a.folder, "name": a.name, "affiliation": a.affiliation}
        for a in AUTHORS
    ]


@app.get("/api/audit/{folder}")
def api_audit(folder: str):
    a = AUTHORS_BY_FOLDER.get(folder)
    if not a:
        raise HTTPException(status_code=404, detail="author not found")
    return audit(a)


@app.get("/api/summary")
def api_summary():
    """Aggregate findings across all 50 authors."""
    results = [audit(a) for a in AUTHORS]
    trust_counts = {"OK": 0, "MEDIUM": 0, "LOW": 0}
    for r in results:
        trust_counts[r["trust"]] += 1
    return {
        "total_authors": len(results),
        "trust_distribution": trust_counts,
        "authors_with_conflicts": sum(
            1 for r in results if r["affiliation_live"]["status"] == "CONFLICT"
        ),
        "authors_with_no_orcid": sum(
            1 for r in results if r["affiliation"]["status"] == "NO_ORCID"
        ),
        "authors_with_file_live_mismatch": sum(
            1 for r in results if r["affiliation_live"].get("file_vs_live_agree") in ("PARTIAL", "DISAGREE")
        ),
    }
