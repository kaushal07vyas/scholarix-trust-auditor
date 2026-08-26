# Scholarix AI Trust Auditor

A focused proof of concept that surfaces trust issues in researcher profile data.

## What it does

Given a folder of researcher profiles (profile.json, publications.json, broad_impact.json),
this tool flags:

1. **Affiliation conflicts** between the stated affiliation and ORCID's institution list
2. **Verification failures** (rate limits, network errors) that were silently swallowed
3. **Publication count mismatches** between stated metrics and actual file contents

Each finding is labeled with a confidence level and a plain-English reason.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
# Point at the authors directory
python -m src.load_authors data/authors
python -m src.checks.affiliation data/authors --out reports/affiliation_conflicts.csv
```

## Data expectations

Each author folder contains:
- `profile.json` — includes `affiliation` (string), `orcid.current_institution` (list), `verification.google_scholar.reason` (nullable string)
- `publications.json` — list of publications with `citations_all` per source
- `broad_impact.json` — list of search results with `category` and `url`

## Layout

```
src/
  load_authors.py       # loads all author folders into a dataframe
  checks/
    affiliation.py      # part A.1 of the profile integrity check
    verification.py     # part A.2 — failed vs never checked
    pub_count.py        # part A.3 — stated vs actual publication count
  clients/
    orcid.py            # ORCID public API with local caching
    openalex.py         # (later) OpenAlex client
    crossref.py         # (later) Crossref client
cache/                  # API response cache (gitignored)
reports/                # generated CSV/JSON outputs (gitignored)
```
