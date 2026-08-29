# Scholarix Trust Auditor

**Repository:** https://github.com/kaushal07vyas/scholarix-trust-auditor

A focused proof of concept for the Scholarix AI evaluation. Given a folder of researcher profiles with claimed verification metadata, this tool independently re-verifies against the live ORCID API and surfaces trust issues that the raw data hides.

## The problem

Scholarix provided data on 50 researchers, three JSON files per author (profile, publications, broad impact). The data looks complete on the surface: ORCID IDs, "verified" flags, institution lists, citation counts. In practice, it silently misleads users:

- 44% of authors have no ORCID at all, yet the data doesn't make that obvious
- 100% of Google Scholar verifications failed with HTTP 429, but the failure looks identical to "verified: false" with no reason
- 100% of personal website, LinkedIn, and ResearchGate verifications were never even attempted
- 90% of authors have `publications.json` truncated to around 100-120 papers vs claimed counts in the thousands
- 64% of authors with a "verified ORCID" have institution lists in the file that don't match what the live ORCID API returns

A grad student, faculty member, or research administrator using this data to make decisions would trust a green checkmark that shouldn't be green.

## What this prototype does

Runs four independent checks per author and presents them in a single trust audit page:

1. **Affiliation vs file's ORCID block** — fuzzy match with a threshold
2. **Affiliation vs live ORCID API** — independent re-verification, plus flags where the file's ORCID data disagrees with live ORCID
3. **Verification channel status** — separates "rate limited" from "fetch error" from "never checked" from "verified", so users can see what actually happened
4. **Publication list completeness** — compares stated publication count to what's actually in the file

Each check outputs a labeled status with a plain-English reason. The dashboard rolls the four into a single trust label (OK / Medium / Low) with the list of specific issues detected.

## Findings

Across the 50 provided authors:

| Metric | Result |
|---|---|
| Total authors | 50 |
| Authors with no ORCID at all | 22 (44%) |
| Authors with live ORCID conflicts | 11 (22%) |
| File ORCID data does not match live ORCID | 18 out of 28 checkable (64%) |
| Google Scholar verifications that failed silently | 50 (100%) |
| Verification channels never even attempted | 150 (personal_website + linkedin + researchgate, all null across all 50) |
| Authors with publication list gaps > 25% | 45 (90%) |
| Authors passing all four checks with no issues | 0 |

Zero of the 50 researchers in the provided dataset have fully trustworthy metadata.

## Architecture

```
src/
  load_authors.py           loads all 50 author folders into memory
  fetch_all_orcid.py        batch-fetches ORCID for every author with an id
  api.py                    FastAPI backend serving the dashboard
  clients/
    orcid.py                ORCID public API client with local disk cache
  checks/
    affiliation.py          profile affiliation vs file's ORCID institutions
    affiliation_live.py     profile affiliation vs live ORCID API
    verification.py         verification channel status classifier
    pub_count.py            publication list completeness
templates/
  index.html                single-page dashboard (Jinja + vanilla JS)
data/authors/               input data (50 author folders, gitignored)
cache/orcid/                ORCID API response cache (gitignored)
reports/                    generated CSV outputs per check
```

## Sources used

**ORCID public API** (`https://pub.orcid.org/v3.0/{id}/record`). No auth required. We use `/record` to pull the full profile and extract employment history. Responses are cached to disk so re-runs cost nothing.

We deliberately scoped to one API rather than adding Crossref, OpenAlex, and Semantic Scholar, because:

- Our chosen product direction is trust in researcher **identity**, not publication metadata
- ORCID is the single source for identity claims in academic data
- Publication-level cross-checking is documented as future scope in the pitch

## Setup

Clone the repository:

```bash
git clone https://github.com/kaushal07vyas/scholarix-trust-auditor.git
cd scholarix-trust-auditor
```

Requires Python 3.10 or newer.

```bash
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt

# drop the provided authors folder at data/authors, then:

# Step 1: sanity check the data loads
python -m src.load_authors data/authors

# Step 2: run each file-level check (writes CSVs to reports/)
python -m src.checks.affiliation data/authors
python -m src.checks.verification data/authors
python -m src.checks.pub_count data/authors

# Step 3: fetch live ORCID records for every author with an id (uses cache)
python -m src.fetch_all_orcid data/authors

# Step 4: run the live affiliation check
python -m src.checks.affiliation_live data/authors

# Step 5: start the dashboard
uvicorn src.api:app --reload
# open http://127.0.0.1:8000
```

The first ORCID batch fetch takes 15-30 seconds. Every response is cached to `cache/orcid/`, so subsequent runs are instant.

## How the trust label works

For each author, we count trust issues surfaced by the four checks:

- 0 issues → **OK**
- 1-2 issues → **Medium**
- 3 or more issues → **Low**

Issues counted:

- Stated affiliation conflicts with the file's ORCID block
- Stated affiliation conflicts with the live ORCID API
- Live ORCID shows no employment history but the file claims institutions
- The file's ORCID block partially or fully disagrees with live ORCID
- Publication list is more than 25% incomplete relative to stated count
- All verification channels failed silently or were never attempted

The label is deliberately conservative. When in doubt, we show uncertainty rather than hide it.

## Handling uncertainty

The rubric emphasizes surfacing uncertainty over hiding it. Design decisions that follow from that:

- The verification check keeps rate limits, network errors, and "never attempted" as distinct labels rather than collapsing them into "unverified"
- The affiliation checks show the best-match candidate and its score, not just a boolean
- The live ORCID check shows both the file's claim and the live data, and labels the disagreement explicitly
- When the ORCID API returns zero institutions but the file claims some, we flag it as `ORCID_NO_EMPLOYMENT` rather than silently trusting the file
- Every check has a `reason` field with a plain-English explanation

## Limitations

- **One API only.** We validate identity, not publications. Publication-level DOI verification, citation cross-checking, and wrong-person detection at the paper level are future scope.
- **Fuzzy matching threshold is heuristic.** We use token-set ratio at 85. Some edge cases (like "UIUC" vs "University of Illinois System") sit near the threshold and could go either way. Threshold tuning would benefit from more label data.
- **ORCID API rate limits are unclear.** Public tier appears generous but not documented precisely. We cache aggressively and add a 100ms delay between fresh requests.
- **No user auth or persistence.** The dashboard is a demo of the audit, not a production system.
- **Publications file is truncated upstream.** The 90% "large gap" finding surfaces the fact that `publications.json` caps at around 100-120 papers per author, which is a data collection issue we cannot fix from our side.

## What we would build next

- Publication-level DOI verification via Crossref
- Wrong-person paper detection using author-list comparison
- Confidence scoring per publication combining OpenAlex, Crossref, and Semantic Scholar
- Batch export of flagged records for admin review
- Correction suggestions when the file disagrees with a live source
- Admin review queue for records requiring human judgment

## Team

- **Kaushal Vyas** — Product & Research Operations (customer discovery, product brief, pitch)
- **Dhruv** — Full Stack Developer (data pipeline, ORCID integration, trust audit logic, dashboard)

## AI/tool usage note

Claude (Anthropic) was used as a pair-programming assistant during development. All API integrations, check logic, and UI code were reviewed and tested by the developer against the provided data. Findings in this README were verified against actual output of the checks.