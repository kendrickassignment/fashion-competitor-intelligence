# Fashion Competitor Intelligence

[![Quality gates](https://github.com/kendrickassignment/fashion-competitor-intelligence/actions/workflows/ci.yml/badge.svg)](https://github.com/kendrickassignment/fashion-competitor-intelligence/actions/workflows/ci.yml)
![Python 3.12](https://img.shields.io/badge/python-3.12-3776AB)
![Destinations](https://img.shields.io/badge/destinations-CSV%20%7C%20PostgreSQL%20%7C%20Google%20Sheets-087E8B)

**A tested ETL pipeline that turns a fictional fashion catalog into a validated pricing dataset and a repeatable competitor-research workflow.**

Built for Dicoding's data-processing submission and extended as a data engineering portfolio project. The source, [Fashion Studio](https://fashion-studio.dicoding.dev/), contains fictional products intended for educational use. This project demonstrates engineering practices; it does not claim access to real competitor sales or promotions.

## Verified results

| Check | Result |
|---|---|
| Extraction | 50 pages, 20 cards per page, 1,000 raw records |
| Clean output | 867 products, 133 quarantined records, 86.7% yield |
| Data quality | No nulls, duplicate product titles, or invalid product attributes in clean output |
| Currency | Fixed **USD 1 = IDR 16,000**, as required by the assignment |
| Destinations | CSV, real PostgreSQL, and Google Sheets; all requested sinks must succeed |
| Tests | 95 passing tests, including a real PostgreSQL integration test |
| Coverage | 100% statements and branches for `src/`, `config.py`, and `main.py` in the recorded test run |

Inspect the [CSV dataset](products.csv), [live review spreadsheet](https://docs.google.com/spreadsheets/d/1lqqDHckLAKN9X9r4-topU6O4Jd9oCJIf7bEmvSzgHPE/edit), and [execution evidence](docs/evidence/README.md). Test results describe the recorded code and environment; future source changes can change row counts. The clean count is observed, not hardcoded.

## Architecture

```mermaid
flowchart LR
    A["Fashion Studio<br/>50 pages / 1,000 cards"] --> B["EXTRACT<br/>retry · timeout · completeness"]
    B --> R["Raw CSV<br/>page and extraction lineage"]
    R --> C["TRANSFORM<br/>IDR conversion · typed contract"]
    C --> Q["Quarantine CSV<br/>original values + rejection reason"]
    C --> D["Quality gate<br/>nonempty · minimum 80% yield"]
    D --> E["CSV snapshot"]
    D --> F["PostgreSQL<br/>current catalog + observations"]
    D --> G["Google Sheets<br/>atomic refresh + full read-back"]
    D --> H["CSV marts<br/>category metrics + observed changes"]
    E & F & G --> I["Run audit<br/>success / failure per destination"]
```

The Python entry point orchestrates separate extraction, transformation, and loading modules. Each storage implementation has its own file. JSON files contain operational reports and checksums; product datasets and analytics marts are CSV, PostgreSQL, or Google Sheets only.

## Run locally

Use **Python 3.12**. Direct dependencies are pinned in `requirements.txt`; transitive versions are constrained by `constraints.txt`. A clean virtual-environment installation, dependency check, lint, and all 95 tests were also verified. Commands below start from the repository root.

```bash
python -m venv .venv
# macOS / Linux
source .venv/bin/activate
# Windows PowerShell
# .venv\Scripts\Activate.ps1

python -m pip install -r requirements.txt
python main.py
```

The default profile scrapes all 50 pages and publishes `products.csv`. It requires no database or Google credentials. An explicit CSV-only run does not claim that remote destinations were tested.

To run all three destinations, start PostgreSQL and configure your service account:

```bash
docker compose up -d --wait
export DATABASE_URL='postgresql+psycopg2://fashion:local-development-only@127.0.0.1:5432/fashion'
export SPREADSHEET_ID='your-spreadsheet-id'
export GOOGLE_APPLICATION_CREDENTIALS='/absolute/private/path/google-sheets-api.json'
python main.py --submission
```

PowerShell environment syntax:

```powershell
$env:DATABASE_URL = 'postgresql+psycopg2://fashion:local-development-only@127.0.0.1:5432/fashion'
$env:SPREADSHEET_ID = 'your-spreadsheet-id'
$env:GOOGLE_APPLICATION_CREDENTIALS = 'C:\private\google-sheets-api.json'
python main.py --submission
```

Enable the Sheets API in the service account's project and share the destination spreadsheet with its `client_email` as an editor. Environment variables are read at runtime; `.env.example` documents them but is not automatically loaded. Compose's password is for a loopback-bound local development database. The provided review sheet is public for the assignment; use your own destination when reproducing the project.

`--submission` requires 50 pages, all three destinations, a database URL, a spreadsheet ID, and an existing credential file. It fails before extraction if configuration is incomplete.

## Data contract

| Column | pandas dtype | Meaning and rules |
|---|---|---|
| `Title` | `object` (string values) | Nonempty product identity; excludes `Unknown Product` |
| `Price` | `float64` | Positive IDR amount, converted once from a valid USD string |
| `Rating` | `float64` | Numeric rating in the inclusive range 0–5 |
| `Colors` | `int64` | Positive integer, without the `Colors` suffix; accepted range 1–100 |
| `Size` | `object` (string values) | XS, S, M, L, XL, XXL, XXXL, or 3XL; no `Size:` prefix |
| `Gender` | `object` (string values) | Men, Women, or Unisex; no `Gender:` prefix |
| `timestamp` | `object` (ISO 8601 string) | UTC extraction time with microseconds and a trailing `Z` |

Raw CSV additionally retains `source_page` and `source_url`. PostgreSQL stores timestamps as `TIMESTAMPTZ`. CSV itself has no dtype metadata: consumers should apply the documented schema when reading it.

Invalid rows retain their original values in quarantine. Each receives the **first failing rule** as its primary reason; reason totals therefore reconcile to the number of rejected rows. Deduplication happens after validation and uses the title identity, excluding extraction timestamps. [Design decisions](docs/DESIGN.md) explain the identity assumption and its limits.

## Reliability behavior

- **Complete extraction:** reject unexpected card counts and repeated page payloads. An exhausted request retry aborts extraction instead of silently skipping a page.
- **Bounded requests:** connect/read timeouts, three transient HTTP retries, backoff, `Retry-After` support, and a delay between sequential page requests.
- **Quality before loading:** validate exact columns, dtypes, finite numbers, domains, UTC timestamps, nulls, and duplicate identities. Every sink revalidates its input.
- **Atomic local files:** flush a temporary file and replace the destination only after a complete write. A failed sink prevents promotion of `products.csv` and `data/latest.csv`.
- **Transactional PostgreSQL:** serialize writers with an advisory lock; replace the current snapshot and insert observation history in one transaction. Replaying an observation does not duplicate history.
- **Atomic Sheets refresh:** resize and write a dedicated `Products` tab in one `batchUpdate`; write literal strings rather than formulas; verify all submitted cells by reading them back.
- **Explicit outcomes:** each requested destination receives a success/failure result. The CLI exits with status 1 on any required failure. Driver messages containing secrets are excluded from the run audit.
- **Replay and audit:** unique run directories retain raw data, quarantine, checksums, quality statistics, timings, and destination outcomes. A local exclusive file lock prevents concurrent writers to the same output directory.

These guarantees apply per destination. There is no distributed transaction across CSV, PostgreSQL, and Sheets: one remote sink can commit before another fails. Safe replay is the recovery mechanism, and the run report records partial delivery. See the [runbook](docs/RUNBOOK.md).

## Outputs and research questions

```text
products.csv                         # last successfully published clean catalog
data/latest.csv                      # previous-success baseline for local comparisons
data/runs/<UTC-time>-<unique-id>/
  raw.csv                            # original values and source lineage
  quarantine.csv                     # original rejected rows and primary reasons
  clean.csv                          # validated per-run snapshot
  category_metrics.csv               # count, price range/median/mean, mean rating
  changes.csv                        # first observed, price changed, observation gaps
  quality.json                       # operational counts and rule accounting
  run.json                           # timings, hashes, destination status
```

`category_metrics.csv` helps analysts compare price distributions by category and gender. `changes.csv` compares successful clean snapshots. A missing product is labeled **`not_observed_clean`**, because invalid source data is not evidence of delisting. With no prior snapshot, the baseline is **`first_observed`**, not a fabricated price change. [SQL examples](sql/analysis.sql) query both current prices and observation history.

Replay an archived raw snapshot without scraping again:

```bash
python main.py --replay docs/evidence/raw.csv --output-dir replay-output
# With all credentials configured, replay to all three destinations:
python main.py --submission --replay docs/evidence/raw.csv
```

Replay preserves the original extraction timestamps. If cleaning rules change, the same raw data may produce a different result; history currently represents observations rather than versioned transformation semantics.

## Tests and automation

```bash
python -m ruff check .
python -m pytest tests --cov --cov-report=term-missing
# Optional real integration test; use a DEDICATED disposable database:
export TEST_DATABASE_URL='postgresql+psycopg2://user:password@127.0.0.1:5432/fashion_test'
python -m pytest tests --cov --cov-report=term-missing
```

All tests live in `tests/`. HTTP calls are mocked and external HTTP is blocked by an autouse fixture. The PostgreSQL integration test exercises real persistence, idempotence, snapshot deletion, and transaction rollback; it removes its tables and must run only against a disposable test database. Without `TEST_DATABASE_URL`, that one test is explicitly skipped. Coverage includes application code and the CLI, excludes tests and maintenance scripts, and CI requires at least 90% **branch-aware** coverage.

[Quality gates](.github/workflows/ci.yml) run lint, tests, and a real PostgreSQL service on pushes and pull requests. Both workflows use Ubuntu 24.04 explicitly and pin their Node.js 24 Actions to verified release commit SHAs. The pip cache key includes both direct requirements and transitive constraints. [Catalog refresh](.github/workflows/catalog.yml) can be dispatched manually or run daily at **01:17 UTC / 08:17 Asia/Jakarta**. It stores run artifacts for 30 days. To enable all remote sinks in that workflow, configure repository secrets `DATABASE_URL`, `SPREADSHEET_ID`, and `GOOGLE_SERVICE_ACCOUNT_JSON`. Without the full configuration, the workflow clearly selects the CSV-only profile. Scheduled comparisons start from the checkout baseline; persistent incremental baselines require durable remote orchestration state.

## Review package

[Submission instructions](submission.txt) map every advanced rubric requirement to its implementation and evidence. The public GitHub repository deliberately excludes private keys. A private submission ZIP can include the required service-account JSON for the authorized reviewer:

```bash
python scripts/build_submission.py --output /private/submission.zip \
  --credentials /private/google-sheets-api.json
```

Do not publish that private ZIP. The key is not needed for offline unit tests or CSV replay. The reviewer must also follow any additional instructions in Dicoding's separate submission tab; those instructions were not supplied with this project.

## Scope and next steps

This is a small, production-minded batch system designed for a 1,000-card educational catalog. It has no distributed scheduler, cross-sink transaction, distributed lock, or managed secrets infrastructure. Title-based identity and the fixed exchange rate are assignment-specific choices. A commercial extension should introduce source product IDs, a versioned data contract, durable orchestration state, managed secrets, freshness alerts, and calibrated quality thresholds before operating at larger scale.
