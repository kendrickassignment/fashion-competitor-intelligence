# Recorded execution evidence

The evidence in this directory comes from a completed live extraction and actual delivery to all three required repositories on **26 October 2026, Asia/Jakarta**. Operational timestamps inside the files use UTC. The source is a fictional educational catalog.

| Artifact | What it establishes |
|---|---|
| [run.json](run.json) | Successful live run, 50 requested pages, explicit successful outcomes for all three destinations, timings and hashes |
| [raw.csv](raw.csv) | 1,000 untransformed source cards, source-page/URL lineage, actual extraction timestamps |
| [clean.csv](clean.csv) | 867 validated products in the required schema; identical to the root `products.csv` |
| [quarantine.csv](quarantine.csv) | 133 original rejected rows with disjoint primary reasons |
| [quality.json](quality.json) | Reconciled counts, 16,000 conversion factor, 86.7% yield, rejection reasons |
| [delivery.json](delivery.json) | Independent CSV validation, all-row PostgreSQL comparison, all-cell Sheets comparison, public editor permission |
| [postgresql.sql](postgresql.sql) | Portable real PostgreSQL table definitions and data, without owner or grant dependencies |
| [tests.json](tests.json) | Recorded test counts, versions, statement coverage, branch coverage, per-module summaries |
| [environment.json](environment.json) | Successful clean installation, dependency check, lint, and 95-test run with resolved package versions |
| [category_metrics.csv](category_metrics.csv) | Generated category/gender price and rating aggregates |
| [changes.csv](changes.csv) | Changes relative to the preceding successful local observation; an empty event table means no observed changes |

The raw-to-clean accounting is **1,000 = 867 + 133**. Primary reasons are 100 invalid titles and 33 invalid prices. A row with both an invalid title and rating is counted once under the first failing rule, not twice.

The database evidence was recorded on an isolated local PostgreSQL 18.1 server. Its current catalog has 867 rows; history contains 1,734 observations from two distinct extraction runs. Replaying a run was also verified without adding duplicate history. The automated integration test additionally verifies rollback after a database insertion failure. CI uses PostgreSQL 16 for portability.

The independent verifier can be rerun while the configured destinations hold this snapshot:

```bash
python scripts/verify_delivery.py --run docs/evidence --output delivery-verification.json
```

It requires the same environment variables as the full pipeline, plus permission to read spreadsheet sharing metadata. Run reports use safe error classes and do not contain private credentials. The public spreadsheet can be edited during review, so future contents may differ from the recorded evidence.

Test coverage measures `src/`, `config.py`, and `main.py`; maintenance and packaging scripts are outside that scope. The recorded 95-test run includes the real database integration test. Without a disposable `TEST_DATABASE_URL`, the integration test is explicitly skipped.
